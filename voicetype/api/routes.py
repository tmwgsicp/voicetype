#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
HTTP/WebSocket API for VoiceType.
Exposes voice typing control, status, and configuration endpoints.
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class StatusResponse(BaseModel):
    ready: bool
    is_recording: bool
    asr_connected: bool
    current_scene: str
    scene_display_name: str
    active_window: str


class SceneOverride(BaseModel):
    scene: str


_app_state = {
    "engine": None,
}


def set_engine(engine):
    _app_state["engine"] = engine


def _get_engine():
    return _app_state["engine"]


@router.get("/status", response_model=StatusResponse)
async def get_status():
    engine = _get_engine()
    if not engine:
        return StatusResponse(
            ready=False,
            is_recording=False,
            asr_connected=False,
            current_scene="general",
            scene_display_name="General",
            active_window="",
        )

    scene = engine.scene_classifier.current_scene
    window = engine.window_watcher.current
    asr_connected = engine._asr_ext is not None and engine._asr_ext.lifecycle.is_ready()
    return StatusResponse(
        ready=True,
        is_recording=engine.is_recording,
        asr_connected=asr_connected,
        current_scene=scene.name,
        scene_display_name=scene.display_name,
        active_window=f"{window.app_name} - {window.window_title}",
    )


@router.get("/check-microphone")
async def check_microphone():
    """检测麦克风是否可用"""
    try:
        import sounddevice as sd
        
        # 检查默认输入设备
        default_input = sd.default.device[0]
        if default_input is None or default_input < 0:
            return {
                "available": False,
                "error": "未检测到默认麦克风",
                "suggestion": "请在系统设置中启用麦克风"
            }
        
        devices = sd.query_devices()
        default_device = devices[default_input]
        
        if default_device['max_input_channels'] == 0:
            return {
                "available": False,
                "error": f"设备 '{default_device['name']}' 不支持录音",
                "suggestion": "请选择支持录音的设备"
            }
        
        # 尝试创建录音流(不实际录音)
        try:
            test_stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype='int16'
            )
            test_stream.close()
            
            return {
                "available": True,
                "device_name": default_device['name'],
                "device_id": default_input
            }
        except Exception as e:
            return {
                "available": False,
                "error": f"麦克风启动失败: {str(e)}",
                "suggestion": "请检查: 1) 麦克风权限 2) 设备是否被占用 3) 驱动是否正常"
            }
            
    except Exception as e:
        logger.error(f"麦克风检测失败: {e}", exc_info=True)
        return {
            "available": False,
            "error": f"检测异常: {str(e)}",
            "suggestion": "请重启应用或系统"
        }


@router.post("/toggle")
async def toggle_recording():
    engine = _get_engine()
    if not engine:
        return {"error": "Engine not initialized"}

    if engine.is_recording:
        await engine.stop_recording()
        return {"recording": False}
    else:
        await engine.start_recording()
        return {"recording": True}


@router.post("/scene")
async def set_scene(override: SceneOverride):
    engine = _get_engine()
    if not engine:
        return {"error": "Engine not initialized"}

    engine.set_scene_override(override.scene if override.scene != "auto" else None)
    return {"scene": override.scene}


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket for real-time status updates and ASR text streaming."""
    await ws.accept()
    engine = _get_engine()

    if not engine:
        await ws.close(code=1011, reason="Engine not initialized")
        return

    engine.add_ws_client(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "toggle":
                if engine.is_recording:
                    await engine.stop_recording()
                else:
                    await engine.start_recording()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error: %s", e)
    finally:
        engine.remove_ws_client(ws)
