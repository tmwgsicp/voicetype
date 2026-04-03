#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
VoiceType entry point.
Starts FastAPI server + VoiceTypingEngine.
When running standalone (not via Tauri), also starts system tray + floating widget.
"""

import argparse
import logging
import os
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .engine import VoiceTypingEngine
from .api.routes import router, set_engine
from .api.config_routes import config_router, set_config
from .api.rule_routes import rule_router
from .api.scene_routes import scene_router, set_scene_engine
from .api.voiceprint_routes import voiceprint_router, set_engine_instance
from .config import load_config, VoiceTypeConfig

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(stream=sys.stderr)],
)
logger = logging.getLogger(__name__)

engine: VoiceTypingEngine = None

# Whether Tauri manages tray/widget (set via --tauri flag)
_tauri_mode = False


def _create_tray_icon(config: VoiceTypeConfig):
    """Create system tray icon (standalone mode only)."""
    try:
        import pystray
        from PIL import Image, ImageDraw

        def _make_icon(color="gray"):
            sz = 64
            img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            accent = (24, 144, 255, 255) if color == "blue" else \
                     (255, 77, 79, 255) if color == "red" else \
                     (140, 140, 140, 255)
            draw.rounded_rectangle([14, 6, 50, 36], radius=10, fill=accent)
            draw.rounded_rectangle([18, 10, 46, 32], radius=7, fill=(255, 255, 255, 255))
            draw.arc([10, 22, 54, 50], start=0, end=180, fill=accent, width=3)
            draw.line([32, 46, 32, 56], fill=accent, width=3)
            draw.line([22, 56, 42, 56], fill=accent, width=3)
            return img

        def on_open_settings(icon, item):
            webbrowser.open(f"http://{config.host}:{config.port}/")

        def on_quit(icon, item):
            icon.stop()
            import signal
            os.kill(os.getpid(), signal.SIGINT)

        menu = pystray.Menu(
            pystray.MenuItem("Open Settings", on_open_settings, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit VoiceType", on_quit),
        )

        _tray_icon = pystray.Icon("VoiceType", _make_icon("gray"), "VoiceType", menu)
        _tray_icon.run()

    except ImportError:
        logger.info("pystray not installed, system tray disabled")
    except Exception as e:
        logger.warning("System tray failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine

    config = load_config()
    set_config(config)

    if not config.llm_api_key:
        logger.error("LLM_API_KEY not set. Please configure in .env or Web UI.")

    engine = VoiceTypingEngine(
        llm_api_key=config.llm_api_key,
        llm_base_url=config.llm_base_url,
        llm_model=config.llm_model,
        asr_provider=config.asr_provider,
        asr_api_key=config.asr_api_key,
        asr_secret_key=config.asr_secret_key,
        asr_model=config.asr_model,
        asr_max_silence_ms=config.asr_max_silence_ms,
        hotkey=config.hotkey,
        typing_delay_ms=config.typing_delay_ms,
    )
    set_engine(engine)
    set_scene_engine(engine)
    set_engine_instance(engine)
    await engine.start()
    
    # 加载并应用持久化的声纹设置
    from .config import get_config_dir
    voiceprint_settings_file = get_config_dir() / "voiceprint_settings.json"
    if voiceprint_settings_file.exists():
        try:
            import json
            with open(voiceprint_settings_file, 'r', encoding='utf-8') as f:
                vp_settings = json.load(f)
                enabled = vp_settings.get("enabled", False)
                engine.set_voiceprint_enabled(enabled)
                logger.info(f"Loaded voiceprint settings: enabled={enabled}")
        except Exception as e:
            logger.warning(f"Failed to load voiceprint settings: {e}")

    logger.info("VoiceType service ready")
    logger.info("ASR: %s", config.asr_model)
    logger.info("LLM: %s @ %s", config.llm_model, config.llm_base_url)
    logger.info("Hotkey: %s (toggle recording)", config.hotkey)
    logger.info("Web UI: http://%s:%d/", config.host, config.port)

    if config.auto_start_asr and config.asr_api_key:
        logger.info("Auto-starting ASR recording...")
        await engine.start_recording()

    if not _tauri_mode:
        tray_thread = threading.Thread(target=_create_tray_icon, args=(config,), daemon=True)
        tray_thread.start()

    yield

    await engine.stop()
    logger.info("VoiceType shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="VoiceType",
        description="Real-time voice-to-text input with AI-powered text cleanup",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.include_router(config_router)
    app.include_router(rule_router)
    app.include_router(scene_router)
    app.include_router(voiceprint_router)

    # Mount static files
    ui_dist = Path(__file__).parent.parent / "src-ui" / "dist"
    if ui_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(ui_dist / "assets")), name="assets")
        
        @app.get("/")
        async def serve_index():
            return FileResponse(str(ui_dist / "index.html"))
        
        @app.get("/floating.html")
        async def serve_floating():
            return FileResponse(str(ui_dist / "floating.html"))

    return app


def run():
    """
    Entry point for `voicetype` command or `python -m voicetype`.
    Supports --port and --tauri flags for Tauri sidecar mode.
    """
    global _tauri_mode

    parser = argparse.ArgumentParser(description="VoiceType Server")
    parser.add_argument("--port", type=int, default=None, help="Server port (overrides config)")
    parser.add_argument("--tauri", action="store_true", help="Running as Tauri sidecar (skip tray/widget)")
    args = parser.parse_args()

    _tauri_mode = args.tauri

    load_dotenv()
    config = load_config()

    port = args.port or int(os.environ.get("VOICETYPE_PORT", 0)) or config.port

    app = create_app()
    uvicorn.run(
        app,
        host=config.host,
        port=port,
        log_level="warning",
    )


if __name__ == "__main__":
    run()
