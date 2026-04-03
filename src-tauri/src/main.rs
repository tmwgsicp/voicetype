// Copyright (C) 2026 VoiceType Contributors
// Licensed under AGPL-3.0

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Child;
use std::sync::Mutex;
use std::net::TcpListener;
use tauri::{
    Manager, RunEvent,
    menu::{MenuBuilder, MenuItemBuilder},
    tray::TrayIconBuilder,
};

mod sidecar;

struct AppState {
    port: Mutex<u16>,
    sidecar_child: Mutex<Option<Child>>,
}

#[tauri::command]
fn get_port(state: tauri::State<AppState>) -> u16 {
    *state.port.lock().unwrap()
}

#[tauri::command]
async fn toggle_recording(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let port = *state.port.lock().unwrap();
    let url = format!("http://127.0.0.1:{}/api/toggle", port);
    let client = reqwest::Client::new();
    let resp = client
        .post(&url)
        .send()
        .await
        .map_err(|e| e.to_string())?;
    let json: serde_json::Value = resp.json().await.map_err(|e| e.to_string())?;
    Ok(json)
}

#[tauri::command]
async fn get_status(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let port = *state.port.lock().unwrap();
    let url = format!("http://127.0.0.1:{}/api/status", port);
    let client = reqwest::Client::new();
    let resp = client.get(&url).send().await.map_err(|e| e.to_string())?;
    let json: serde_json::Value = resp.json().await.map_err(|e| e.to_string())?;
    Ok(json)
}

fn main() {
    // 单实例检测：尝试绑定特定端口作为互斥锁
    let _lock_listener = match TcpListener::bind("127.0.0.1:38765") {
        Ok(listener) => {
            // 成功绑定，说明没有其他实例在运行
            Some(listener)
        }
        Err(_) => {
            // 端口已被占用，说明已有实例在运行
            eprintln!("VoiceType is already running!");
            std::process::exit(1);
        }
    };

    let port = portpicker::pick_unused_port().expect("No available port");

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_process::init())
        .manage(AppState {
            port: Mutex::new(port),
            sidecar_child: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            get_port,
            toggle_recording,
            get_status,
        ])
        .setup(move |app| {
            let handle = app.handle().clone();

            // Build tray menu
            let show_item = MenuItemBuilder::with_id("show", "Open Settings").build(app)?;
            let quit_item = MenuItemBuilder::with_id("quit", "Quit VoiceType").build(app)?;
            let menu = MenuBuilder::new(app)
                .item(&show_item)
                .separator()
                .item(&quit_item)
                .build()?;

            TrayIconBuilder::new()
                .tooltip("VoiceType")
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(move |app_handle, event| {
                    match event.id().as_ref() {
                        "show" => {
                            if let Some(w) = app_handle.get_webview_window("main") {
                                let _ = w.show();
                                let _ = w.unminimize();
                                let _ = w.set_focus();
                            }
                        }
                        "quit" => {
                            app_handle.exit(0);
                        }
                        _ => {}
                    }
                })
                .build(app)?;

            // Prevent main window from closing, just hide it
            let main_window = app.get_webview_window("main").unwrap();
            let main_window_clone = main_window.clone();
            main_window.on_window_event(move |event| {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    main_window_clone.hide().unwrap();
                    api.prevent_close();
                }
            });

            // Spawn Python sidecar
            let sidecar_handle = handle.clone();
            let state = handle.state::<AppState>();
            match sidecar::spawn_sidecar(&sidecar_handle, port) {
                Ok(child) => {
                    eprintln!("[TAURI] ✓ Python sidecar spawned successfully, PID: {}", child.id());
                    *state.sidecar_child.lock().unwrap() = Some(child);
                }
                Err(e) => {
                    eprintln!("[TAURI] ✗ FAILED to spawn Python sidecar: {}", e);
                    log::error!("Failed to spawn sidecar: {}", e);
                }
            }

            // Health check polling in background
            let health_handle = handle.clone();
            tauri::async_runtime::spawn(async move {
                sidecar::wait_for_ready(&health_handle, port).await;
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let RunEvent::ExitRequested { .. } = &event {
                // Kill sidecar on exit
                let state = app_handle.state::<AppState>();
                let mut guard = state.sidecar_child.lock().unwrap();
                if let Some(mut child) = guard.take() {
                    let _ = child.kill();
                }
            }
        });
}
