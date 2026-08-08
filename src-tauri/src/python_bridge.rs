use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStderr, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::{Arc, Mutex};
use std::time::Duration;

type PendingSender = Sender<Result<serde_json::Value, String>>;

/// Python 子进程桥接
///
/// 通过 stdin/stdout JSON 行协议与 Python 通信。
/// stdout 由独立 reader 线程读取，并按响应 ID 分发到对应的 call，
/// 因此多个 Tauri 命令可以同时等待 Python 响应。
/// stderr 用于日志流，由外部线程读取；stdout 的事件由独立 receiver 转发。
pub struct PythonBridge {
    child: Mutex<Option<Child>>,
    stdin: Mutex<ChildStdin>,
    stderr: Mutex<Option<ChildStderr>>,
    next_id: AtomicU64,
    pending: Arc<Mutex<HashMap<u64, PendingSender>>>,
    event_receiver: Mutex<Option<Receiver<serde_json::Value>>>,
    /// 取消当前可取消 call 的 Rust 等待，同时通过独立 RPC 通知 Python 任务。
    cancelled: AtomicBool,
    /// 当前可取消 RPC 的请求 ID，用于让 Python 精确匹配取消目标。
    cancellable_request_id: AtomicU64,
}

/// 启动 stdout reader：响应按 ID 投递，异步事件单独投递。
fn spawn_reader(
    stdout: ChildStdout,
    pending: Arc<Mutex<HashMap<u64, PendingSender>>>,
    event_sender: Sender<serde_json::Value>,
) {
    std::thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        loop {
            let mut line = String::new();
            match reader.read_line(&mut line) {
                Ok(0) => break,
                Ok(_) => {}
                Err(_) => break,
            }

            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }

            let parsed: serde_json::Value = match serde_json::from_str(trimmed) {
                Ok(value) => value,
                Err(_) => continue,
            };

            if parsed.get("event").is_some() {
                let _ = event_sender.send(parsed);
                continue;
            }

            let Some(response_id) = parsed.get("id").and_then(|value| value.as_u64()) else {
                continue;
            };

            let sender = pending
                .lock()
                .ok()
                .and_then(|mut requests| requests.remove(&response_id));
            if let Some(sender) = sender {
                let _ = sender.send(Ok(parsed));
            }
        }

        // Python 进程退出时唤醒所有等待中的调用，避免永久阻塞。
        let requests = pending
            .lock()
            .map(|mut requests| {
                requests
                    .drain()
                    .map(|(_, sender)| sender)
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default();
        for sender in requests {
            let _ = sender.send(Err("Python process exited unexpectedly".into()));
        }
    });
}

fn is_cancellable_method(method: &str) -> bool {
    matches!(
        method,
        "process_fuel"
            | "process_production"
            | "process_electrical"
            | "process_worktime"
            | "process_merge"
            | "process_maintenance"
            | "process_maintenance_llm"
            | "batch_process"
            | "sync_minebase"
    )
}

impl PythonBridge {
    /// 启动 Python 子进程
    ///
    /// `python_cmd` 可以是 "python3" 或 "uv run python3"。
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
        Self::from_child(child, stdin, stdout, stderr)
    }

    /// 从可执行文件路径直接启动（sidecar 模式）。
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
        Self::from_child(child, stdin, stdout, stderr)
    }

    fn from_child(
        child: Child,
        stdin: ChildStdin,
        stdout: ChildStdout,
        stderr: Option<ChildStderr>,
    ) -> Result<Self, String> {
        let pending = Arc::new(Mutex::new(HashMap::new()));
        let (event_sender, event_receiver) = mpsc::channel();
        spawn_reader(stdout, Arc::clone(&pending), event_sender);

        Ok(Self {
            child: Mutex::new(Some(child)),
            stdin: Mutex::new(stdin),
            stderr: Mutex::new(stderr),
            next_id: AtomicU64::new(1),
            pending,
            event_receiver: Mutex::new(Some(event_receiver)),
            cancelled: AtomicBool::new(false),
            cancellable_request_id: AtomicU64::new(0),
        })
    }

    /// 取出 stdout 异步事件 receiver（只能调用一次）。
    pub fn take_event_receiver(&self) -> Option<Receiver<serde_json::Value>> {
        self.event_receiver.lock().ok()?.take()
    }

    /// 取出 stderr 句柄（只能调用一次）。
    pub fn take_stderr(&self) -> Option<ChildStderr> {
        self.stderr.lock().ok()?.take()
    }

    fn next_request_id(&self) -> u64 {
        self.next_id.fetch_add(1, Ordering::Relaxed)
    }

    fn clear_cancellable_request(&self, request_id: u64) {
        let _ = self.cancellable_request_id.compare_exchange(
            request_id,
            0,
            Ordering::SeqCst,
            Ordering::SeqCst,
        );
    }

    fn write_request(
        &self,
        request_id: u64,
        method: &str,
        params: &serde_json::Value,
    ) -> Result<(), String> {
        let request = serde_json::json!({
            "id": request_id,
            "method": method,
            "params": params,
        });
        let request_line =
            serde_json::to_string(&request).map_err(|e| format!("JSON encode error: {}", e))?;

        let mut stdin = self.stdin.lock().map_err(|e| e.to_string())?;
        writeln!(stdin, "{}", request_line).map_err(|e| format!("Write to stdin failed: {}", e))?;
        stdin
            .flush()
            .map_err(|e| format!("Flush stdin failed: {}", e))
    }

    /// 发送 RPC 请求并等待对应 ID 的响应。
    ///
    /// 这里只锁住 stdin 写入，不锁住整个响应等待过程。
    pub fn call(
        &self,
        method: &str,
        params: &serde_json::Value,
    ) -> Result<serde_json::Value, String> {
        let cancellable = is_cancellable_method(method);
        let request_id = self.next_request_id();
        if cancellable {
            self.cancelled.store(false, Ordering::SeqCst);
            self.cancellable_request_id
                .store(request_id, Ordering::SeqCst);
        }

        let (sender, receiver) = mpsc::channel();

        self.pending
            .lock()
            .map_err(|e| e.to_string())?
            .insert(request_id, sender);

        if let Err(error) = self.write_request(request_id, method, params) {
            if let Ok(mut requests) = self.pending.lock() {
                requests.remove(&request_id);
            }
            if cancellable {
                self.clear_cancellable_request(request_id);
            }
            return Err(error);
        }

        loop {
            if cancellable && self.cancelled.load(Ordering::SeqCst) {
                if let Ok(mut requests) = self.pending.lock() {
                    requests.remove(&request_id);
                }
                self.clear_cancellable_request(request_id);
                return Err("Task cancelled".into());
            }

            match receiver.recv_timeout(Duration::from_millis(100)) {
                Ok(Ok(response)) => {
                    if let Some(error) = response.get("error") {
                        let fallback = error.to_string();
                        let message = error.as_str().unwrap_or(&fallback);
                        if cancellable {
                            self.clear_cancellable_request(request_id);
                        }
                        return Err(message.to_string());
                    }
                    if let Some(result) = response.get("result") {
                        if cancellable {
                            self.clear_cancellable_request(request_id);
                        }
                        return Ok(result.clone());
                    }
                    if cancellable {
                        self.clear_cancellable_request(request_id);
                    }
                    return Err(format!("Unexpected response: {}", response));
                }
                Ok(Err(error)) => {
                    if cancellable {
                        self.clear_cancellable_request(request_id);
                    }
                    return Err(error);
                }
                Err(mpsc::RecvTimeoutError::Timeout) => continue,
                Err(mpsc::RecvTimeoutError::Disconnected) => {
                    if cancellable {
                        self.clear_cancellable_request(request_id);
                    }
                    return Err("Python process exited unexpectedly".into());
                }
            }
        }
    }

    /// 发送无需等待响应的控制请求。
    fn send_notification(&self, method: &str, params: &serde_json::Value) {
        let request_id = self.next_request_id();
        let _ = self.write_request(request_id, method, params);
    }

    /// 取消当前任务：立即结束 Rust 侧等待，并通知 Python 设置任务令牌。
    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::SeqCst);
        let request_id = self.cancellable_request_id.load(Ordering::SeqCst);
        let params = if request_id == 0 {
            serde_json::json!({})
        } else {
            serde_json::json!({"request_id": request_id})
        };
        self.send_notification("cancel", &params);

        // LLM 处理器还会在网络请求间隔中读取这个文件，保留文件信号作为兜底。
        if let Ok(home) = std::env::var("HOME") {
            let cancel_path = std::path::PathBuf::from(home)
                .join(".cache")
                .join("mining_processor_cancel");
            let _ = std::fs::create_dir_all(cancel_path.parent().unwrap());
            let _ = std::fs::write(cancel_path, "cancel");
        }
    }

    /// 获取子进程 PID（用于前端展示）。
    pub fn pid(&self) -> Option<u32> {
        self.child.lock().ok()?.as_ref().map(|c| c.id())
    }

    /// 检查子进程是否仍在运行。
    pub fn is_alive(&self) -> bool {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(ref mut child) = *guard {
                return child.try_wait().ok().flatten().is_none();
            }
        }
        false
    }
}

impl Drop for PythonBridge {
    fn drop(&mut self) {
        if let Ok(mut child_guard) = self.child.lock() {
            if let Some(mut child) = child_guard.take() {
                let _ = child.kill();
                let _ = child.wait();
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

    fn temp_script(name: &str, content: &str) -> PathBuf {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system clock must be after the Unix epoch")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "mining_processor_python_bridge_{}_{}_{}.py",
            name,
            std::process::id(),
            stamp,
        ));
        std::fs::write(&path, content).expect("test Python script must be writable");
        path
    }

    #[test]
    fn concurrent_calls_are_routed_by_response_id() {
        let script_path = temp_script(
            "concurrent",
            r#"
import json
import sys
import threading
import time

def handle(request):
    if request["method"] == "long_running":
        time.sleep(0.5)
    print(json.dumps({"id": request["id"], "result": {"method": request["method"]}}), flush=True)

for line in sys.stdin:
    threading.Thread(target=handle, args=(json.loads(line),), daemon=True).start()
"#,
        );

        let python = if cfg!(windows) { "python" } else { "python3" };
        let bridge = Arc::new(
            PythonBridge::new(python, script_path.to_str().expect("UTF-8 temp path"))
                .expect("Python bridge must start"),
        );
        let long_bridge = Arc::clone(&bridge);
        let long_call =
            std::thread::spawn(move || long_bridge.call("long_running", &serde_json::json!({})));

        std::thread::sleep(Duration::from_millis(50));
        let started = Instant::now();
        let quick_result = bridge.call("ping", &serde_json::json!({}));

        assert_eq!(quick_result, Ok(serde_json::json!({"method": "ping"})),);
        assert!(started.elapsed() < Duration::from_millis(400));
        assert_eq!(
            long_call.join().expect("long call must finish"),
            Ok(serde_json::json!({"method": "long_running"})),
        );

        drop(bridge);
        let _ = std::fs::remove_file(&script_path);
    }

    #[test]
    fn cancel_interrupts_a_call_waiting_for_python() {
        let script_path = temp_script(
            "cancel",
            r#"
import json
import sys
import time

for line in sys.stdin:
    request = json.loads(line)
    time.sleep(1 if request["method"] == "process_production" else 0)
    print(json.dumps({"id": request["id"], "result": {"ok": True}}), flush=True)
"#,
        );

        let python = if cfg!(windows) { "python" } else { "python3" };
        let bridge = Arc::new(
            PythonBridge::new(python, script_path.to_str().expect("UTF-8 temp path"))
                .expect("Python bridge must start"),
        );
        let call_bridge = Arc::clone(&bridge);
        let call = std::thread::spawn(move || {
            call_bridge.call("process_production", &serde_json::json!({}))
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

        let next_result = bridge.call("ping", &serde_json::json!({}));
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

    #[test]
    fn cancel_notification_targets_the_active_request() {
        let script_path = temp_script(
            "cancel_target",
            r#"
import json
import sys
import threading
import time

process_id = [None]
cancel_request_id = [None]
cancelled = threading.Event()

def handle(request):
    method = request["method"]
    if method == "process_production":
        process_id[0] = request["id"]
        cancelled.wait(2)
        time.sleep(0.3)
        print(json.dumps({"id": request["id"], "result": {"ok": True}}), flush=True)
    elif method == "cancel":
        cancel_request_id[0] = request["params"].get("request_id")
        cancelled.set()
        print(json.dumps({"id": request["id"], "result": {"ok": True}}), flush=True)
    elif method == "ping":
        print(json.dumps({
            "id": request["id"],
            "result": {"cancel_request_id": cancel_request_id[0]},
        }), flush=True)

for line in sys.stdin:
    threading.Thread(
        target=handle,
        args=(json.loads(line),),
        daemon=True,
    ).start()
"#,
        );

        let python = if cfg!(windows) { "python" } else { "python3" };
        let bridge = Arc::new(
            PythonBridge::new(python, script_path.to_str().expect("UTF-8 path"))
                .expect("Python bridge must start"),
        );
        let call_bridge = Arc::clone(&bridge);
        let call = std::thread::spawn(move || {
            call_bridge.call("process_production", &serde_json::json!({}))
        });

        std::thread::sleep(Duration::from_millis(100));
        bridge.cancel();
        assert_eq!(
            call.join().expect("call thread must finish"),
            Err("Task cancelled".to_string())
        );

        let ping = bridge.call("ping", &serde_json::json!({}));
        assert_eq!(ping, Ok(serde_json::json!({"cancel_request_id": 1})));

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
