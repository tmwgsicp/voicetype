#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
VoiceType configuration management.
Supports layered config: defaults < config.json < .env < runtime API updates.

Version-based Configuration Migration System:
- Each config has a `config_version` field tracking schema version
- Migrations are defined declaratively in MIGRATIONS list
- Automatic backup before migration
- Forward-only migration (no downgrade)
"""

import json
import logging
import os
import sys
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Current config schema version
CURRENT_CONFIG_VERSION = 2  # v0.3.0: sherpa default + keyring support


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

    # Config Version (for migration tracking)
    config_version: int = Field(
        default=CURRENT_CONFIG_VERSION,
        description="Config schema version for automatic migration"
    )

    # ASR Provider
    asr_provider: str = Field(
        default="sherpa",
        description="ASR provider: sherpa (default, local offline), aliyun, or tencent"
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
    asr_vad_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="VAD sensitivity threshold (0.0-1.0, higher = less sensitive, default: 0.5)"
    )
    sherpa_model_dir: str = Field(
        default="models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20",
        description="Sherpa-ONNX ASR model directory path"
    )
    sherpa_kws_model_dir: str = Field(
        default="models/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01",
        description="Sherpa-ONNX KWS model directory path"
    )
    sherpa_keywords: List[str] = Field(
        default_factory=lambda: ["语音输入", "开始输入"],
        description="Custom wake words for keyword spotting"
    )
    sherpa_kws_enabled: bool = Field(
        default=False,
        description="Enable keyword spotting (wake word detection)"
    )

    # LLM
    llm_api_key: str = Field(default="", description="LLM API Key")
    llm_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="LLM API base URL (OpenAI-compatible endpoint)",
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


# ============================================================================
# Configuration Migration System
# ============================================================================

def migrate_v0_to_v1(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate from v0 (no version field) to v1.
    
    Changes:
    - Add config_version field
    """
    logger.info("Migrating config from v0 → v1")
    data["config_version"] = 1
    return data


def migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate from v1 to v2 (v0.3.0).
    
    Changes:
    - Default ASR: aliyun → sherpa (local offline)
    - Remove bundled API keys (security)
    - Add keyring support (API keys moved to OS credential store)
    """
    logger.info("Migrating config from v1 → v2 (v0.3.0)")
    
    # Detect legacy default config (aliyun + bundled API key)
    if data.get("asr_provider") == "aliyun":
        asr_key = data.get("asr_api_key", "")
        # If using bundled key (starts with sk-), switch to local ASR
        if asr_key.startswith("sk-"):
            logger.warning("Detected bundled API key, switching to local ASR")
            data["asr_provider"] = "sherpa"
            data["asr_model"] = "sherpa-local"
            data.pop("asr_api_key", None)
        # If user configured their own key, keep aliyun but warn
        elif asr_key:
            logger.info("User-configured Aliyun key detected, keeping cloud ASR")
    
    # Update version
    data["config_version"] = 2
    return data


# Migration pipeline: list of (target_version, migration_function)
MIGRATIONS: List[tuple[int, Callable[[Dict[str, Any]], Dict[str, Any]]]] = [
    (1, migrate_v0_to_v1),
    (2, migrate_v1_to_v2),
]


def backup_config(config_path: Path) -> Optional[Path]:
    """Create timestamped backup of config file."""
    if not config_path.exists():
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = config_path.parent / f"config.backup.{timestamp}.json"
    
    try:
        shutil.copy2(config_path, backup_path)
        logger.info(f"Config backed up to: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to backup config: {e}")
        return None


def apply_migrations(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply all necessary migrations to bring config to current version.
    
    Args:
        data: Raw config dict loaded from config.json
    
    Returns:
        Migrated config dict at CURRENT_CONFIG_VERSION
    """
    current_version = data.get("config_version", 0)
    
    if current_version == CURRENT_CONFIG_VERSION:
        logger.debug(f"Config already at v{CURRENT_CONFIG_VERSION}, no migration needed")
        return data
    
    if current_version > CURRENT_CONFIG_VERSION:
        logger.warning(
            f"Config version {current_version} > app version {CURRENT_CONFIG_VERSION}. "
            "This may be from a newer VoiceType version. Attempting to load anyway..."
        )
        return data
    
    # Apply migrations sequentially
    logger.info(f"Migrating config: v{current_version} → v{CURRENT_CONFIG_VERSION}")
    
    for target_version, migration_func in MIGRATIONS:
        if current_version < target_version:
            try:
                data = migration_func(data)
                logger.info(f"✓ Migration to v{target_version} complete")
            except Exception as e:
                logger.error(f"✗ Migration to v{target_version} failed: {e}")
                raise
    
    return data


def load_config() -> VoiceTypeConfig:
    """
    Load config with priority: defaults < config.json < .env
    
    Automatic migration:
    1. Load raw config.json
    2. Detect version and apply migrations
    3. Backup old config before migration
    4. Save migrated config
    """
    config = VoiceTypeConfig()

    logger.info(f"Loading config from: {CONFIG_FILE}")
    config_path = CONFIG_FILE
    
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_data = json.load(f)
            
            current_version = file_data.get("config_version", 0)
            
            # Apply migrations if needed
            if current_version < CURRENT_CONFIG_VERSION:
                logger.info(f"Config migration needed: v{current_version} → v{CURRENT_CONFIG_VERSION}")
                
                # Backup before migration
                backup_config(config_path)
                
                # Apply all necessary migrations
                file_data = apply_migrations(file_data)
                
                # Merge with defaults and validate
                config = VoiceTypeConfig(**{**config.model_dump(), **file_data})
                
                # Save migrated config
                save_config(config)
                logger.info("✓ Config migration complete and saved")
            else:
                # No migration needed, just load
                config = VoiceTypeConfig(**{**config.model_dump(), **file_data})
                logger.info(f"✓ Loaded config v{current_version} from {CONFIG_FILE}")
                
        except Exception as e:
            logger.warning("Failed to load %s: %s", CONFIG_FILE, e)

    # Environment variable overrides (highest priority)
    env_map = {
        "ASR_PROVIDER": "asr_provider",
        "ASR_API_KEY": "asr_api_key",
        "ASR_SECRET_KEY": "asr_secret_key",
        "ASR_MODEL": "asr_model",
        "ASR_MAX_SILENCE_MS": "asr_max_silence_ms",
        "ASR_VAD_THRESHOLD": "asr_vad_threshold",
        "SHERPA_MODEL_DIR": "sherpa_model_dir",
        "SHERPA_KWS_MODEL_DIR": "sherpa_kws_model_dir",
        "SHERPA_KEYWORDS": "sherpa_keywords",
        "SHERPA_KWS_ENABLED": "sherpa_kws_enabled",
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

            # Special handling for list types (comma-separated)
            if config_key == "sherpa_keywords":
                overrides[config_key] = [k.strip() for k in val.split(",")]
            elif field_type == int:
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
    """
    Persist config to config.json.
    
    Note: 
    - 优先使用 OS Keyring 存储 API Keys（Tauri 前端负责）
    - 如果 Keyring 不可用，API Keys 会保存到 config.json（降级方案）
    - 开发环境使用 .env 文件
    """
    data = config.model_dump()
    
    # 空值不保存（使用默认值）
    if not data.get("llm_base_url"):
        data.pop("llm_base_url", None)
    
    # 注意：API Keys 现在会保存到 config.json（降级方案）
    # 如果 Keyring 可用，前端会自动清理这些字段

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Config saved to %s", CONFIG_FILE)


def mask_key(key: str) -> str:
    """Mask API key for display: sk-abc...xyz"""
    if not key or len(key) < 10:
        return "***"
    return key[:6] + "..." + key[-4:]
