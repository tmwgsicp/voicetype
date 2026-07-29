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

/// 把编辑菜单窗设为「非激活」窗口（WS_EX_NOACTIVATE + TOOLWINDOW）。
/// 这样它弹出/被点击时都不会抢走目标程序的焦点——目标程序里的文字选区得以保留，
/// 套用改写时粘贴才能正确「替换」而不是「插入到前面」。
#[cfg(windows)]
fn make_edit_menu_noactivate(app: &tauri::AppHandle) {
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        GetWindowLongPtrW, SetWindowLongPtrW, GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW,
    };
    if let Some(win) = app.get_webview_window("edit-menu") {
        if let Ok(hwnd) = win.hwnd() {
            let h = hwnd.0 as _;
            unsafe {
                let ex = GetWindowLongPtrW(h, GWL_EXSTYLE);
                SetWindowLongPtrW(
                    h,
                    GWL_EXSTYLE,
                    ex | WS_EX_NOACTIVATE as isize | WS_EX_TOOLWINDOW as isize,
                );
            }
            log::info!("edit-menu window set to no-activate");
        }
    }
}

#[cfg(not(windows))]
fn make_edit_menu_noactivate(_app: &tauri::AppHandle) {}

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
fn hide_edit_menu(app: tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("edit-menu") {
        let _ = w.hide();
    }
}

#[tauri::command]
fn show_main_window(app: tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.unminimize();
        let _ = w.set_focus();
    }
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
            show_main_window,
            hide_edit_menu,
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

            // 编辑菜单窗设为非激活，避免抢焦点导致选区丢失（否则粘贴会变成插入而非替换）
            make_edit_menu_noactivate(&handle);

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
