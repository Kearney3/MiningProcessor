use std::io::{BufRead, BufReader, Write};
use std::process::{ChildStderr, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;

/// Python 子进程桥接
///
/// 通过 stdin/stdout JSON 行协议与 Python 通信。
/// stderr 用于日志流，由外部线程读取。
pub struct PythonBridge {
    stdin: Mutex<ChildStdin>,
    stdout: Mutex<BufReader<ChildStdout>>,
    stderr: Mutex<Option<ChildStderr>>,
    next_id: Mutex<u64>,
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

        // 子进程句柄不再需要持有，stdin 关闭时进程会自动退出
        // 但为了安全，我们泄漏它让它在后台运行
        std::mem::forget(child);

        Ok(Self {
            stdin: Mutex::new(stdin),
            stdout: Mutex::new(BufReader::new(stdout)),
            stderr: Mutex::new(stderr),
            next_id: Mutex::new(1),
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

        std::mem::forget(child);

        Ok(Self {
            stdin: Mutex::new(stdin),
            stdout: Mutex::new(BufReader::new(stdout)),
            stderr: Mutex::new(stderr),
            next_id: Mutex::new(1),
        })
    }

    /// 取出 stderr 句柄（只能调用一次）
    ///
    /// 返回 `Some(ChildStderr)` 首次调用时，之后返回 `None`。
    pub fn take_stderr(&self) -> Option<ChildStderr> {
        self.stderr.lock().ok()?.take()
    }

    /// 发送 RPC 请求并等待响应
    pub fn call(&self, method: &str, params: &serde_json::Value) -> Result<serde_json::Value, String> {
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

        // 读取 stdout 响应（跳过异步事件）
        loop {
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

impl Drop for PythonBridge {
    fn drop(&mut self) {
        // stdin 被 drop 时管道关闭，Python 进程会收到 EOF 并退出
    }
}
