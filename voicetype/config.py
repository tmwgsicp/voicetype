#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
VoiceType configuration management.
Supports layered config: defaults < config.json < .env < runtime API updates.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def get_config_dir() -> Path:
    """
    Get persistent config directory for VoiceType.
    获取持久化配置目录。
    """
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if appdata:
            config_dir = Path(appdata) / "VoiceType"
        else:
            config_dir = Path.home() / "VoiceType"
    elif sys.platform == "darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "VoiceType"
    else:
        config_dir = Path.home() / ".config" / "voicetype"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


CONFIG_FILE = get_config_dir() / "config.json"


class VoiceTypeConfig(BaseModel):
    """Complete VoiceType configuration."""

    # ASR Provider
    asr_provider: str = Field(
        default="aliyun",
        description="ASR provider: aliyun (default) or tencent"
    )
    
    # ASR Credentials
    asr_api_key: str = Field(
        default="",
        description="ASR API Key (Aliyun DashScope API Key or Tencent SecretId)"
    )
    asr_secret_key: str = Field(
        default="",
        description="Tencent Cloud SecretKey (only required for tencent provider)"
    )
    
    # ASR Model Configuration
    asr_model: str = Field(
        default="qwen3-asr-flash-realtime",
        description="ASR model (aliyun: qwen3-asr-*, tencent: 16k_zh/16k_zh_en/16k_en)"
    )
    asr_max_silence_ms: int = Field(
        default=1200,
        description="VAD silence threshold in milliseconds (500-2000, default: 1200)"
    )

    # LLM
    llm_api_key: str = Field(default="", description="LLM API Key")
    llm_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="LLM API base URL",
    )
    llm_model: str = Field(
        default="qwen-turbo",
        description="LLM model"
    )
    llm_temperature: float = Field(default=0.3, description="LLM temperature")
    llm_max_tokens: int = Field(default=200, description="LLM max output tokens")

    # Hotkey
    hotkey: str = Field(default="<f9>", description="Toggle hotkey (pynput format)")

    # Output
    typing_delay_ms: int = Field(default=5, description="Typing delay between chars (ms)")

    # Server
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=18233, description="Server port")

    # Auto-start
    auto_start_asr: bool = Field(default=False, description="Auto-start recording on launch")

    # Voiceprint
    voiceprint_enabled: bool = Field(default=False, description="Enable voiceprint recognition")
    voiceprint_provider: str = Field(
        default="local",
        description="Voiceprint provider: local (sherpa-onnx), aliyun, tencent, or iflytek"
    )
    voiceprint_threshold: float = Field(
        default=0.6,
        description="Voiceprint similarity threshold (0.0-1.0, higher = stricter)"
    )


def load_config() -> VoiceTypeConfig:
    """Load config with priority: defaults < config.json < .env"""
    config = VoiceTypeConfig()

    logger.info(f"Loading config from: {CONFIG_FILE}")
    config_path = CONFIG_FILE
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_data = json.load(f)
            config = VoiceTypeConfig(**{**config.model_dump(), **file_data})
            logger.info("Loaded config from %s", CONFIG_FILE)
        except Exception as e:
            logger.warning("Failed to load %s: %s", CONFIG_FILE, e)

    env_map = {
        "ASR_PROVIDER": "asr_provider",
        "ASR_API_KEY": "asr_api_key",
        "ASR_SECRET_KEY": "asr_secret_key",
        "ASR_MODEL": "asr_model",
        "ASR_MAX_SILENCE_MS": "asr_max_silence_ms",
        "LLM_API_KEY": "llm_api_key",
        "LLM_BASE_URL": "llm_base_url",
        "LLM_MODEL": "llm_model",
        "LLM_TEMPERATURE": "llm_temperature",
        "LLM_MAX_TOKENS": "llm_max_tokens",
        "HOTKEY": "hotkey",
        "TYPING_DELAY_MS": "typing_delay_ms",
        "HOST": "host",
        "PORT": "port",
        "AUTO_START_ASR": "auto_start_asr",
        "VOICEPRINT_ENABLED": "voiceprint_enabled",
        "VOICEPRINT_PROVIDER": "voiceprint_provider",
        "VOICEPRINT_THRESHOLD": "voiceprint_threshold",
    }

    overrides = {}
    for env_key, config_key in env_map.items():
        val = os.getenv(env_key)
        if val is not None:
            field_info = VoiceTypeConfig.model_fields[config_key]
            field_type = field_info.annotation

            if field_type == int:
                overrides[config_key] = int(val)
            elif field_type == float:
                overrides[config_key] = float(val)
            elif field_type == bool:
                overrides[config_key] = val.lower() in ("true", "1", "yes")
            else:
                overrides[config_key] = val

    if overrides:
        config = VoiceTypeConfig(**{**config.model_dump(), **overrides})

    return config


def save_config(config: VoiceTypeConfig):
    """Persist config to config.json."""
    data = config.model_dump()
    data.pop("asr_api_key", None)
    data.pop("llm_api_key", None)

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Config saved to %s", CONFIG_FILE)


def mask_key(key: str) -> str:
    """Mask API key for display: sk-abc...xyz"""
    if not key or len(key) < 10:
        return "***"
    return key[:6] + "..." + key[-4:]
