mod python_bridge;

use python_bridge::PythonBridge;
use tauri::{Emitter, Manager, State};

/// 应用状态，PythonBridge 自身的内部锁已保证线程安全。
/// 不再需要外层 Mutex<Option<PythonBridge>>，避免 cancel_task 与 invoke_python 的死锁 (H1)。
struct AppState {
    bridge: PythonBridge,
    mode: String,
    command: String,
}

#[tauri::command]
async fn invoke_python(
    method: String,
    params: serde_json::Value,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    state.bridge.call(&method, &params)
}

#[tauri::command]
async fn cancel_task(state: State<'_, AppState>) -> Result<(), String> {
    state.bridge.cancel();
    Ok(())
}

#[tauri::command]
async fn get_bridge_info(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({
        "mode": state.mode,
        "pid": state.bridge.pid(),
        "alive": state.bridge.is_alive(),
        "command": state.command,
    }))
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

/// 查找 sidecar 二进制的候选路径（跨平台）
/// onedir 模式下 sidecar 是一个目录，exe 在目录内
fn sidecar_candidates(exe_dir: &std::path::Path) -> Vec<std::path::PathBuf> {
    let mut candidates = vec![
        exe_dir.join("tauri-bridge"),
    ];

    // Windows: 带 .exe 后缀 + onedir 目录结构
    #[cfg(target_os = "windows")]
    {
        candidates.push(exe_dir.join("tauri-bridge.exe"));
        // onedir 模式：sidecar 目录在 exe 同级（resources 目录）
        candidates.push(exe_dir.join("tauri-bridge/tauri-bridge.exe"));
    }

    // macOS .app bundle 结构
    #[cfg(target_os = "macos")]
    {
        candidates.push(exe_dir.join("../MacOS/tauri-bridge"));
        candidates.push(exe_dir.join("../../MacOS/tauri-bridge"));
        // onedir 模式：sidecar 目录在 Resources 目录
        candidates.push(exe_dir.join("../Resources/tauri-bridge/tauri-bridge"));
        candidates.push(exe_dir.join("../../Resources/tauri-bridge/tauri-bridge"));
    }

    candidates
}

/// 尝试以 sidecar 模式启动（打包后）
///
/// 按优先级在多个路径查找 sidecar 二进制。
fn try_start_sidecar(app: &tauri::App) -> Option<PythonBridge> {
    let exe_dir = std::env::current_exe().ok()?.parent()?.to_path_buf();

    // Tauri resource_dir 提供最准确的资源目录路径
    let resource_dir = app.path().resource_dir().ok();
    let mut candidates = sidecar_candidates(&exe_dir);

    // 追加 resource_dir 下的候选路径
    if let Some(ref res_dir) = resource_dir {
        #[cfg(target_os = "windows")]
        {
            candidates.push(res_dir.join("tauri-bridge").join("tauri-bridge.exe"));
            candidates.push(res_dir.join("tauri-bridge.exe"));
        }
        #[cfg(target_os = "macos")]
        {
            candidates.push(res_dir.join("tauri-bridge").join("tauri-bridge"));
            candidates.push(res_dir.join("tauri-bridge"));
        }
    }

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

/// 初始化 PythonBridge，优先 sidecar 模式，回退 dev 模式。
/// 在 setup 中调用，直接写入 AppState。
fn init_bridge(app: &tauri::App) -> Result<(), String> {
    // 优先尝试 sidecar 模式（打包后）
    if let Some(bridge) = try_start_sidecar(app) {
        let pid = bridge.pid();
        spawn_stderr_logger(&bridge, app.handle());
        let _ = app.handle().emit("python-log", &serde_json::json!({
            "event": "connection",
            "data": { "status": "connected", "mode": "sidecar", "pid": pid }
        }));
        app.manage(AppState {
            bridge,
            mode: "sidecar".into(),
            command: "tauri-bridge (sidecar)".into(),
        });
        println!("Python bridge started (sidecar mode)");
        return Ok(());
    }

    // 回退到 dev 模式（直接调 Python）
    if let Some((bridge, info)) = try_start_dev() {
        let pid = bridge.pid();
        spawn_stderr_logger(&bridge, app.handle());
        let _ = app.handle().emit("python-log", &serde_json::json!({
            "event": "connection",
            "data": { "status": "connected", "mode": "dev", "pid": pid, "command": info }
        }));
        app.manage(AppState {
            bridge,
            mode: "dev".into(),
            command: info,
        });
        println!("Python bridge started (dev mode)");
        return Ok(());
    }

    // 两种模式都失败，向前端发送错误事件
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_string_lossy().to_string()))
        .unwrap_or_else(|| "unknown".into());
    let resource_dir = app.path().resource_dir()
        .map(|p| p.display().to_string())
        .unwrap_or_else(|_| "unknown".into());
    let searched: Vec<String> = sidecar_candidates(std::path::Path::new(&exe_dir))
        .iter()
        .map(|p| p.display().to_string())
        .collect();
    let msg = format!(
        "Python bridge 未找到。已搜索：exe_dir={} resource_dir={} 候选={}。\
         请确保已运行 PyInstaller 打包 sidecar 并嵌入应用。",
        exe_dir, resource_dir, searched.join("、")
    );
    eprintln!("Warning: {}", msg);
    let _ = app.handle().emit("python-log", &serde_json::json!({
        "event": "connection",
        "data": { "status": "error", "error": msg }
    }));
    let _ = app.handle().emit("python-log", &serde_json::json!({
        "event": "log",
        "data": { "level": "ERROR", "message": msg }
    }));
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            init_bridge(app).unwrap_or_else(|e| eprintln!("Bridge init warning: {}", e));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![invoke_python, cancel_task, get_bridge_info])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
