// Copyright (C) 2026 VoiceType Contributors
// Licensed under AGPL-3.0

use std::process::{Child, Command, Stdio};
use std::io::{BufRead, BufReader};
use tauri::{AppHandle, Emitter, Manager};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

/// Spawn the Python sidecar process with the given port.
pub fn spawn_sidecar(handle: &AppHandle, port: u16) -> Result<Child, String> {
    // 开发模式：直接运行 Python 模块
    #[cfg(debug_assertions)]
    {
        log::info!("Dev mode: Starting Python backend with python -m voicetype.main");
        
        // 获取项目根目录（src-tauri 的父目录）
        let current_dir = std::env::current_dir()
            .map_err(|e| format!("Failed to get current dir: {}", e))?;
        log::info!("Current dir: {:?}", current_dir);
        
        // 如果当前在 src-tauri，需要返回上级
        let project_root = if current_dir.ends_with("src-tauri") {
            current_dir.parent().unwrap().to_path_buf()
        } else {
            current_dir
        };
        
        log::info!("Project root: {:?}", project_root);
        
        let mut cmd = Command::new("python");
        cmd.args(["-m", "voicetype.main", "--port", &port.to_string(), "--tauri"])
            .current_dir(&project_root)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        
        // Windows: 隐藏控制台窗口
        #[cfg(target_os = "windows")]
        {
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }
        
        log::info!("Spawning Python backend...");
        eprintln!("[TAURI] Attempting to spawn Python: python -m voicetype.main --port {} --tauri", port);
        eprintln!("[TAURI] Working directory: {:?}", project_root);
        
        let mut child = cmd.spawn()
            .map_err(|e| {
                let err_msg = format!("Failed to spawn Python backend: {}. Make sure Python is installed and voicetype module is available.", e);
                eprintln!("[TAURI] ✗ {}", err_msg);
                err_msg
            })?;
        
        log::info!("Python backend spawned with PID: {}", child.id());
        eprintln!("[TAURI] ✓ Python backend spawned with PID: {}", child.id());

        // 重要：不要捕获stdout/stderr，让Python直接输出到终端
        // 这样用户可以在同一个终端看到所有日志
        
        // 重要：不要捕获stdout/stderr，让Python直接输出到终端
        // Stream stdout to console
        if let Some(stdout) = child.stdout.take() {
            std::thread::spawn(move || {
                let reader = BufReader::new(stdout);
                for line in reader.lines() {
                    if let Ok(text) = line {
                        eprintln!("[python] {}", text);
                    }
                }
            });
        }
        
        // Stream stderr to console
        if let Some(stderr) = child.stderr.take() {
            std::thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines() {
                    if let Ok(text) = line {
                        eprintln!("[python] {}", text);
                    }
                }
            });
        }
        
        return Ok(child);
    }
    
    // 生产模式：使用打包的 exe
    #[cfg(not(debug_assertions))]
    {
        // 获取资源目录（打包后Python后端在这里）
        let resource_dir = handle
            .path()
            .resource_dir()
            .map_err(|e| format!("Failed to get resource dir: {}", e))?;
        
        // Tauri会将 ../dist/voicetype-server 打包到 _up_/dist/voicetype-server
        let backend_dir = resource_dir.join("_up_").join("dist").join("voicetype-server");
        let exe_path = backend_dir.join(if cfg!(target_os = "windows") {
            "voicetype-server.exe"
        } else {
            "voicetype-server"
        });
        
        if !exe_path.exists() {
            return Err(format!("Backend not found at: {:?}", exe_path));
        }
        
        log::info!("Starting Python backend: {:?}", exe_path);
        log::info!("Working directory: {:?}", backend_dir);
        
        let mut cmd = Command::new(&exe_path);
        cmd.args(["--port", &port.to_string(), "--tauri"])
            .current_dir(&backend_dir)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        
        // Windows: 隐藏控制台窗口
        #[cfg(target_os = "windows")]
        {
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }
        
        let mut child = cmd.spawn()
            .map_err(|e| format!("Failed to spawn backend: {}", e))?;
        
        // Stream stdout to logs
        if let Some(stdout) = child.stdout.take() {
            let log_handle = handle.clone();
            std::thread::spawn(move || {
                let reader = BufReader::new(stdout);
                for line in reader.lines() {
                    if let Ok(text) = line {
                        log::info!("[sidecar] {}", text);
                    }
                }
                let _ = log_handle.emit("sidecar-terminated", ());
            });
        }
        
        // Stream stderr to logs
        if let Some(stderr) = child.stderr.take() {
            std::thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines() {
                    if let Ok(text) = line {
                        log::warn!("[sidecar] {}", text);
                    }
                }
            });
        }
        
        return Ok(child);
    }
}

/// Poll the Python backend until it reports ready, then show windows.
pub async fn wait_for_ready(handle: &AppHandle, port: u16) {
    let url = format!("http://127.0.0.1:{}/api/status", port);
    let client = reqwest::Client::new();

    let max_attempts = 120;
    for attempt in 1..=max_attempts {
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;

        match client.get(&url).send().await {
            Ok(resp) => {
                if let Ok(json) = resp.json::<serde_json::Value>().await {
                    let ready = json.get("ready").and_then(|v| v.as_bool()).unwrap_or(false);

                    // Emit progress to frontend
                    let _ = handle.emit("backend-status", &json);

                    if ready {
                        log::info!("Backend ready after {} attempts", attempt);
                        show_windows(handle);

                        // Start WebSocket relay for recording state
                        let ws_handle = handle.clone();
                        tauri::async_runtime::spawn(async move {
                            relay_ws_events(&ws_handle, port).await;
                        });
                        return;
                    }
                }
            }
            Err(_) => {
                if attempt % 10 == 0 {
                    log::info!("Waiting for backend... attempt {}/{}", attempt, max_attempts);
                }
            }
        }
    }

    log::error!("Backend did not become ready in time");
    // Show windows anyway so user can see the error state
    show_windows(handle);
}

fn show_windows(handle: &AppHandle) {
    if let Some(main_win) = handle.get_webview_window("main") {
        let _ = main_win.show();
        let _ = main_win.set_focus();
    }
    if let Some(float_win) = handle.get_webview_window("floating") {
        let _ = float_win.show();
        // Position floating window at horizontal center, lower portion (above taskbar)
        if let Some(main_win) = handle.get_webview_window("main") {
            if let Ok(monitor) = main_win.current_monitor() {
                if let Some(monitor) = monitor {
                    let size = monitor.size();
                    // 水平居中：x = (屏幕宽度 - 窗口宽度) / 2
                    let x = (size.width as i32 - 170) / 2;
                    // 距离底部 120px（留空间给任务栏）
                    let y = size.height as i32 - 52 - 120;
                    let _ = float_win.set_position(tauri::Position::Physical(
                        tauri::PhysicalPosition::new(x, y),
                    ));
                }
            }
        }
    }
}

/// Connect to Python backend WebSocket and relay recording events to Tauri frontend.
async fn relay_ws_events(handle: &AppHandle, port: u16) {
    use tokio_tungstenite::connect_async;
    use futures_util::StreamExt;

    let ws_url = format!("ws://127.0.0.1:{}/api/ws", port);

    loop {
        match connect_async(&ws_url).await {
            Ok((mut ws, _)) => {
                log::info!("WebSocket relay connected");
                while let Some(Ok(msg)) = ws.next().await {
                    if let tokio_tungstenite::tungstenite::Message::Text(text) = msg {
                        if let Ok(json) = serde_json::from_str::<serde_json::Value>(&text) {
                            let _ = handle.emit("backend-event", &json);
                        }
                    }
                }
                log::warn!("WebSocket relay disconnected, reconnecting...");
            }
            Err(e) => {
                log::warn!("WebSocket relay connect failed: {}, retrying...", e);
            }
        }
        tokio::time::sleep(std::time::Duration::from_secs(3)).await;
    }
}
