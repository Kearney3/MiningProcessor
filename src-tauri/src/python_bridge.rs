use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStderr, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;

/// Python 子进程桥接
///
/// 通过 stdin/stdout JSON 行协议与 Python 通信。
/// stderr 用于日志流，由外部线程读取。
pub struct PythonBridge {
    child: Mutex<Option<Child>>,
    stdin: Mutex<ChildStdin>,
    stdout: Mutex<BufReader<ChildStdout>>,
    stderr: Mutex<Option<ChildStderr>>,
    next_id: Mutex<u64>,
    /// 整个 call 往返的锁，序列化 stdin 写入 + stdout 读取，
    /// 防止并发 RPC 调用响应错配 (H3)
    call_lock: Mutex<()>,
    /// 取消标志，cancel_task 设置后 invoke_python 在读取循环中检查 (H1)
    cancelled: AtomicBool,
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

        Ok(Self {
            child: Mutex::new(Some(child)),
            stdin: Mutex::new(stdin),
            stdout: Mutex::new(BufReader::new(stdout)),
            stderr: Mutex::new(stderr),
            next_id: Mutex::new(1),
            call_lock: Mutex::new(()),
            cancelled: AtomicBool::new(false),
        })
    }

    /// 从可执行文件路径直接启动（sidecar 模式）
    pub fn from_command(binary_path: &std::path::Path) -> Result<Self, String> {
        let mut cmd = Command::new(binary_path);
        cmd.stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("Failed to spawn sidecar: {}", e))?;

        let stdin = child.stdin.take().ok_or("Failed to open stdin")?;
        let stdout = child.stdout.take().ok_or("Failed to open stdout")?;
        let stderr = child.stderr.take();

        Ok(Self {
            child: Mutex::new(Some(child)),
            stdin: Mutex::new(stdin),
            stdout: Mutex::new(BufReader::new(stdout)),
            stderr: Mutex::new(stderr),
            next_id: Mutex::new(1),
            call_lock: Mutex::new(()),
            cancelled: AtomicBool::new(false),
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
    pub fn call(&self, method: &str, params: &serde_json::Value) -> Result<serde_json::Value, String> {
        // 序列化整个往返，防止响应错配
        let _guard = self.call_lock.lock().map_err(|e| e.to_string())?;

        // 重置取消标志
        self.cancelled.store(false, Ordering::SeqCst);

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
            stdin.flush().map_err(|e| format!("Flush stdin failed: {}", e))?;
        }

        // 读取 stdout 响应（跳过异步事件，匹配请求 ID）
        loop {
            // 检查取消标志 (H1)
            if self.cancelled.load(Ordering::SeqCst) {
                return Err("Task cancelled".into());
            }

            let mut line = String::new();
            {
                let mut stdout = self.stdout.lock().map_err(|e| e.to_string())?;
                let bytes_read = stdout
                    .read_line(&mut line)
                    .map_err(|e| format!("Read from stdout failed: {}", e))?;
                if bytes_read == 0 {
                    return Err("Python process exited unexpectedly".into());
                }
            }

            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }

            let response: serde_json::Value =
                serde_json::from_str(trimmed).map_err(|e| {
                    let preview = if trimmed.len() > 200 {
                        format!("{}... ({} bytes total)", &trimmed[..200], trimmed.len())
                    } else {
                        trimmed.to_string()
                    };
                    format!("JSON parse error: {} (line: {})", e, preview)
                })?;

            // 异步事件（无 id）→ 跳过，继续读取
            if response.get("event").is_some() {
                continue;
            }

            // 检查响应 ID 是否匹配当前请求 (H3)
            if let Some(resp_id) = response.get("id").and_then(|v| v.as_u64()) {
                if resp_id != id {
                    // 响应不属于当前请求，跳过
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

    /// 设置取消标志，通知正在执行的 call 提前返回 (H1)
    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::SeqCst);
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
