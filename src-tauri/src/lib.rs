mod python_bridge;

use python_bridge::PythonBridge;
use std::sync::Mutex;
use tauri::{Emitter, Manager, State};

struct AppState {
    bridge: Mutex<Option<PythonBridge>>,
}

#[tauri::command]
async fn invoke_python(
    method: String,
    params: serde_json::Value,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let bridge_guard = state.bridge.lock().map_err(|e| e.to_string())?;
    let bridge = bridge_guard.as_ref().ok_or("Python bridge not initialized")?;
    bridge.call(&method, &params)
}

#[tauri::command]
async fn cancel_task(state: State<'_, AppState>) -> Result<(), String> {
    let bridge_guard = state.bridge.lock().map_err(|e| e.to_string())?;
    let bridge = bridge_guard.as_ref().ok_or("Python bridge not initialized")?;
    bridge.call("cancel", &serde_json::json!({}))?;
    Ok(())
}

/// 查找 Python 解释器（dev 模式）
fn find_python() -> Result<String, String> {
    let candidates = ["uv run python3", "python3", "python"];
    for cmd in &candidates {
        let parts: Vec<&str> = cmd.split_whitespace().collect();
        let status = std::process::Command::new(parts[0])
            .args(&parts[1..])
            .arg("--version")
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status();
        if status.map(|s| s.success()).unwrap_or(false) {
            return Ok(cmd.to_string());
        }
    }
    Err("Python not found".into())
}

/// 查找 tauri_bridge.py 脚本（dev 模式）
fn find_bridge_script() -> Result<std::path::PathBuf, String> {
    let search_paths = [
        std::path::PathBuf::from("tauri_bridge.py"),
        std::path::PathBuf::from("../tauri_bridge.py"),
        std::path::PathBuf::from("../../tauri_bridge.py"),
    ];
    for candidate in &search_paths {
        if candidate.exists() {
            return Ok(candidate.canonicalize().unwrap_or(candidate.clone()));
        }
    }
    Err("tauri_bridge.py not found".into())
}

/// 尝试以 sidecar 模式启动（打包后）
///
/// 在可执行文件同目录下查找 `tauri-bridge` 二进制。
/// 对于 macOS .app bundle，位于 Contents/MacOS/tauri-bridge。
fn try_start_sidecar() -> Option<PythonBridge> {
    let exe_dir = std::env::current_exe().ok()?.parent()?.to_path_buf();

    let candidates = [
        exe_dir.join("tauri-bridge"),
        exe_dir.join("../MacOS/tauri-bridge"),      // 从 Resources 目录
        exe_dir.join("../../MacOS/tauri-bridge"),    // 从嵌套目录
    ];

    for candidate in &candidates {
        if candidate.exists() {
            return PythonBridge::from_command(candidate).ok();
        }
    }
    None
}

/// 尝试以 dev 模式启动（直接调 Python）
fn try_start_dev() -> Option<(PythonBridge, String)> {
    let python_cmd = find_python().ok()?;
    let bridge_script = find_bridge_script().ok()?;
    let cmd_str = format!("{} {}", python_cmd, bridge_script.display());
    PythonBridge::new(&python_cmd, &bridge_script.to_string_lossy())
        .ok()
        .map(|b| (b, cmd_str))
}

/// 启动 stderr 日志转发线程
fn spawn_stderr_logger(bridge: &PythonBridge, handle: &tauri::AppHandle) {
    if let Some(stderr) = bridge.take_stderr() {
        let handle = handle.clone();
        std::thread::spawn(move || {
            use std::io::{BufRead, BufReader};
            let reader = BufReader::new(stderr);
            for line in reader.lines() {
                match line {
                    Ok(line) => {
                        if let Ok(log_event) =
                            serde_json::from_str::<serde_json::Value>(&line)
                        {
                            let _ = handle.emit("python-log", &log_event);
                        } else {
                            let _ = handle.emit(
                                "python-log",
                                &serde_json::json!({
                                    "event": "log",
                                    "data": { "level": "STDERR", "message": line }
                                }),
                            );
                        }
                    }
                    Err(_) => break,
                }
            }
        });
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(AppState {
            bridge: Mutex::new(None),
        })
        .setup(|app| {
            // 优先尝试 sidecar 模式（打包后）
            if let Some(bridge) = try_start_sidecar() {
                spawn_stderr_logger(&bridge, app.handle());
                let state: State<AppState> = app.state();
                let mut guard = state.bridge.lock().unwrap();
                *guard = Some(bridge);
                println!("Python bridge started (sidecar mode)");
                return Ok(());
            }

            // 回退到 dev 模式（直接调 Python）
            if let Some((bridge, info)) = try_start_dev() {
                spawn_stderr_logger(&bridge, app.handle());
                let state: State<AppState> = app.state();
                let mut guard = state.bridge.lock().unwrap();
                *guard = Some(bridge);
                println!("Python bridge started (dev mode): {}", info);
                return Ok(());
            }

            // 两种模式都失败，向前端发送错误事件
            let exe_dir = std::env::current_exe()
                .ok()
                .and_then(|p| p.parent().map(|d| d.to_string_lossy().to_string()))
                .unwrap_or_else(|| "unknown".into());
            let msg = format!(
                "Python bridge 未找到。已搜索：{}/tauri-bridge（sidecar）和系统 Python（dev 模式）。\
                 请确保已运行 build.sh 打包 sidecar，或在开发模式下运行 pnpm tauri dev。",
                exe_dir
            );
            eprintln!("Warning: {}", msg);
            let _ = app.handle().emit("python-log", &serde_json::json!({
                "event": "log",
                "data": { "level": "ERROR", "message": msg }
            }));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![invoke_python, cancel_task])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
