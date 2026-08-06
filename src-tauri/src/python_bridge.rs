use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStderr, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver};
use std::sync::{Arc, Mutex};
use std::time::Duration;

/// 从 reader 线程发送到 call() 的消息
enum BridgeMsg {
    /// 带 id 的 RPC 响应
    Response(serde_json::Value),
    /// 不带 id 的异步事件
    Event(serde_json::Value),
}

/// Python 子进程桥接
///
/// 通过 stdin/stdout JSON 行协议与 Python 通信。
/// stdout 由独立 reader 线程读取，通过 channel 转发给 call()，
/// 使得 cancel() 可以立即中断正在进行的 call()。
/// stderr 用于日志流，由外部线程读取。
pub struct PythonBridge {
    child: Mutex<Option<Child>>,
    stdin: Mutex<ChildStdin>,
    rx: Mutex<Receiver<BridgeMsg>>,
    stderr: Mutex<Option<ChildStderr>>,
    next_id: Mutex<u64>,
    /// 整个 call 往返的锁，序列化 stdin 写入 + 响应匹配，
    /// 防止并发 RPC 调用响应错配 (H3)
    call_lock: Mutex<()>,
    /// 取消标志，cancel_task 设置后 call() 在超时循环中检查 (H1)
    cancelled: Arc<AtomicBool>,
    /// 上一次 call 中因取消而未消费的响应，供下次 call 复用
    pending: Mutex<HashMap<u64, serde_json::Value>>,
}

/// 启动 reader 线程：持续从 stdout 读取 JSON 行，通过 channel 转发
fn spawn_reader(stdout: ChildStdout) -> Receiver<BridgeMsg> {
    let (tx, rx) = mpsc::channel();
    std::thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        loop {
            let mut line = String::new();
            match reader.read_line(&mut line) {
                Ok(0) => break, // EOF: Python 进程已退出
                Ok(_) => {}
                Err(_) => break,
            }
            let trimmed = line.trim().to_string();
            if trimmed.is_empty() {
                continue;
            }
            let parsed: serde_json::Value = match serde_json::from_str(&trimmed) {
                Ok(v) => v,
                Err(_) => continue,
            };
            let msg = if parsed.get("event").is_some() {
                BridgeMsg::Event(parsed)
            } else {
                BridgeMsg::Response(parsed)
            };
            if tx.send(msg).is_err() {
                break; // 接收端已关闭
            }
        }
    });
    // reader 线程独立运行，handle 被丢弃后线程在后台继续工作
    rx
}

impl PythonBridge {
    /// 启动 Python 子进程
    ///
    /// `python_cmd` 可以是 "python3" 或 "uv run python3"
    /// `bridge_script` 是 tauri_bridge.py 的路径
    pub fn new(python_cmd: &str, bridge_script: &str) -> Result<Self, String> {
        let parts: Vec<&str> = python_cmd.split_whitespace().collect();
        let (program, args) = parts.split_first().ok_or("Empty python command")?;

        let mut cmd = Command::new(program);
        cmd.args(args)
            .arg(bridge_script)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("Failed to spawn Python process: {}", e))?;

        let stdin = child.stdin.take().ok_or("Failed to open stdin")?;
        let stdout = child.stdout.take().ok_or("Failed to open stdout")?;
        let stderr = child.stderr.take();
        let cancelled = Arc::new(AtomicBool::new(false));

        let rx = spawn_reader(stdout);

        Ok(Self {
            child: Mutex::new(Some(child)),
            stdin: Mutex::new(stdin),
            rx: Mutex::new(rx),
            stderr: Mutex::new(stderr),
            next_id: Mutex::new(1),
            call_lock: Mutex::new(()),
            cancelled,
            pending: Mutex::new(HashMap::new()),
        })
    }

    /// 从可执行文件路径直接启动（sidecar 模式）
    pub fn from_command(binary_path: &std::path::Path) -> Result<Self, String> {
        let mut cmd = Command::new(binary_path);
        cmd.stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            // 强制 UTF-8 输出，避免中文 Windows 使用 GBK 编码
            .env("PYTHONUTF8", "1")
            .env("PYTHONIOENCODING", "utf-8");

        // Windows: 隐藏控制台窗口
        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            // CREATE_NO_WINDOW = 0x08000000
            cmd.creation_flags(0x08000000);
        }

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("Failed to spawn sidecar: {}", e))?;

        let stdin = child.stdin.take().ok_or("Failed to open stdin")?;
        let stdout = child.stdout.take().ok_or("Failed to open stdout")?;
        let stderr = child.stderr.take();
        let cancelled = Arc::new(AtomicBool::new(false));

        let rx = spawn_reader(stdout);

        Ok(Self {
            child: Mutex::new(Some(child)),
            stdin: Mutex::new(stdin),
            rx: Mutex::new(rx),
            stderr: Mutex::new(stderr),
            next_id: Mutex::new(1),
            call_lock: Mutex::new(()),
            cancelled,
            pending: Mutex::new(HashMap::new()),
        })
    }

    /// 取出 stderr 句柄（只能调用一次）
    ///
    /// 返回 `Some(ChildStderr)` 首次调用时，之后返回 `None`。
    pub fn take_stderr(&self) -> Option<ChildStderr> {
        self.stderr.lock().ok()?.take()
    }

    /// 发送 RPC 请求并等待响应
    ///
    /// 整个写入 + 读取过程由 `call_lock` 序列化，防止并发调用时响应错配 (H3)。
    pub fn call<F>(
        &self,
        method: &str,
        params: &serde_json::Value,
        mut on_event: F,
    ) -> Result<serde_json::Value, String>
    where
        F: FnMut(&serde_json::Value),
    {
        // 序列化整个往返，防止响应错配
        let _guard = self.call_lock.lock().map_err(|e| e.to_string())?;

        // 重置取消标志
        self.cancelled.store(false, Ordering::SeqCst);

        // 清除上次取消残留的响应
        if let Ok(mut p) = self.pending.lock() {
            p.clear();
        }

        let id = {
            let mut id = self.next_id.lock().map_err(|e| e.to_string())?;
            let current = *id;
            *id += 1;
            current
        };

        let request = serde_json::json!({
            "id": id,
            "method": method,
            "params": params,
        });

        let request_line =
            serde_json::to_string(&request).map_err(|e| format!("JSON encode error: {}", e))?;

        // 写入 stdin
        {
            let mut stdin = self.stdin.lock().map_err(|e| e.to_string())?;
            writeln!(stdin, "{}", request_line)
                .map_err(|e| format!("Write to stdin failed: {}", e))?;
            stdin
                .flush()
                .map_err(|e| format!("Flush stdin failed: {}", e))?;
        }

        // 从 channel 接收响应（每 500ms 检查一次取消标志）
        let rx = self.rx.lock().map_err(|e| e.to_string())?;
        loop {
            if self.cancelled.load(Ordering::SeqCst) {
                return Err("Task cancelled".into());
            }

            let msg = match rx.recv_timeout(Duration::from_millis(500)) {
                Ok(msg) => msg,
                Err(mpsc::RecvTimeoutError::Timeout) => continue,
                Err(mpsc::RecvTimeoutError::Disconnected) => {
                    return Err("Python process exited unexpectedly".into());
                }
            };

            match msg {
                BridgeMsg::Event(ref event) => {
                    on_event(event);
                }
                BridgeMsg::Response(ref response) => {
                    // 检查响应 ID 是否匹配当前请求 (H3)
                    if let Some(resp_id) = response.get("id").and_then(|v| v.as_u64()) {
                        if resp_id != id {
                            // 存储非当前请求的响应（供后续 call 复用）
                            if let Ok(mut p) = self.pending.lock() {
                                p.insert(resp_id, response.clone());
                            }
                            continue;
                        }
                    }

                    // 错误响应
                    if let Some(error) = response.get("error") {
                        let fallback = error.to_string();
                        let msg = error.as_str().unwrap_or(&fallback);
                        return Err(msg.to_string());
                    }

                    // 成功响应
                    if let Some(result) = response.get("result") {
                        return Ok(result.clone());
                    }

                    return Err(format!("Unexpected response: {}", response));
                }
            }
        }
    }

    /// 设置取消标志，通知正在执行的 call 提前返回 (H1)
    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::SeqCst);
        // Write cancel signal file for Python-side detection.
        if let Ok(home) = std::env::var("HOME") {
            let cancel_path = std::path::PathBuf::from(home)
                .join(".cache")
                .join("mining_processor_cancel");
            let _ = std::fs::create_dir_all(cancel_path.parent().unwrap());
            let _ = std::fs::write(cancel_path, "cancel");
        }
    }

    /// 获取子进程 PID（用于前端展示）
    pub fn pid(&self) -> Option<u32> {
        self.child.lock().ok()?.as_ref().map(|c| c.id())
    }

    /// 检查子进程是否仍在运行
    pub fn is_alive(&self) -> bool {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(ref mut c) = *guard {
                return c.try_wait().ok().flatten().is_none();
            }
        }
        false
    }
}

impl Drop for PythonBridge {
    fn drop(&mut self) {
        // 关闭 stdin 让 Python 进程读到 EOF 并退出
        // 同时 kill + wait 子进程，防止僵尸进程 (H2)
        if let Ok(mut child_guard) = self.child.lock() {
            if let Some(mut c) = child_guard.take() {
                let _ = c.kill();
                let _ = c.wait();
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::PythonBridge;
    use std::path::PathBuf;
    use std::sync::Arc;
    use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

    #[test]
    fn cancel_interrupts_a_call_waiting_for_python() {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system clock must be after the Unix epoch")
            .as_nanos();
        let script_path = std::env::temp_dir().join(format!(
            "mining_processor_python_bridge_cancel_{}_{}.py",
            std::process::id(),
            stamp,
        ));
        std::fs::write(
            &script_path,
            r#"
import json
import sys
import time

for line in sys.stdin:
    request = json.loads(line)
    time.sleep(1 if request["method"] == "long_running" else 0)
    print(json.dumps({"id": request["id"], "result": {"ok": True}}), flush=True)
"#,
        )
        .expect("test Python script must be writable");

        let python = if cfg!(windows) { "python" } else { "python3" };
        let bridge = Arc::new(
            PythonBridge::new(python, script_path.to_str().expect("UTF-8 temp path"))
                .expect("Python bridge must start"),
        );
        let call_bridge = Arc::clone(&bridge);
        let call = std::thread::spawn(move || {
            call_bridge.call("long_running", &serde_json::json!({}), |_| {})
        });

        std::thread::sleep(Duration::from_millis(100));
        let cancelled_at = Instant::now();
        bridge.cancel();
        let result = call.join().expect("call thread must finish");

        assert_eq!(result, Err("Task cancelled".to_string()));
        assert!(
            cancelled_at.elapsed() < Duration::from_secs(2),
            "cancelled call should return promptly"
        );

        let next_result = bridge.call("ping", &serde_json::json!({}), |_| {});
        assert_eq!(next_result, Ok(serde_json::json!({"ok": true})));

        drop(bridge);
        let _ = std::fs::remove_file(&script_path);
        if let Ok(home) = std::env::var("HOME") {
            let cancel_path = PathBuf::from(home)
                .join(".cache")
                .join("mining_processor_cancel");
            let _ = std::fs::remove_file(cancel_path);
        }
    }
}
