#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Configuration management API.
Allows the Web UI to read/update VoiceType settings.
"""

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import VoiceTypeConfig, save_config, mask_key

logger = logging.getLogger(__name__)

config_router = APIRouter(prefix="/api/config")

_current_config: Optional[VoiceTypeConfig] = None
_engine_instance = None  # Reference to VoiceTypingEngine for hot reload


def set_config(config: VoiceTypeConfig):
    global _current_config
    _current_config = config


def set_engine(engine):
    """Set engine instance for hot reload support."""
    global _engine_instance
    _engine_instance = engine


class ConfigResponse(BaseModel):
    """Config response with masked API keys."""
    asr_provider: str
    asr_api_key: str
    asr_secret_key: str
    asr_model: str
    asr_max_silence_ms: int
    asr_vad_threshold: float
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_temperature: float
    hotkey: str
    typing_delay_ms: int
    host: str
    port: int
    auto_start_asr: bool
    # Voiceprint configuration
    voiceprint_enabled: bool
    voiceprint_provider: str
    voiceprint_threshold: float
    # Sherpa-ONNX ASR configuration
    sherpa_model_dir: str
    # KWS configuration
    sherpa_kws_enabled: bool
    sherpa_kws_model_dir: str
    sherpa_keywords: list[str]


@config_router.get("", response_model=ConfigResponse)
async def get_config():
    """Get current configuration (API keys masked)."""
    if not _current_config:
        return ConfigResponse(**VoiceTypeConfig().model_dump())

    data = _current_config.model_dump()
    data["asr_api_key"] = mask_key(_current_config.asr_api_key)
    data["asr_secret_key"] = mask_key(_current_config.asr_secret_key)
    data["llm_api_key"] = mask_key(_current_config.llm_api_key)
    
    # 确保 llm_base_url 总是有值（使用默认值）
    if not data.get("llm_base_url"):
        data["llm_base_url"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    return ConfigResponse(**data)


class ConfigUpdate(BaseModel):
    asr_provider: Optional[str] = None
    asr_api_key: Optional[str] = None
    asr_secret_key: Optional[str] = None
    asr_model: Optional[str] = None
    asr_max_silence_ms: Optional[int] = None
    asr_vad_threshold: Optional[float] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    hotkey: Optional[str] = None
    typing_delay_ms: Optional[int] = None
    auto_start_asr: Optional[bool] = None
    # Voiceprint configuration
    voiceprint_enabled: Optional[bool] = None
    voiceprint_provider: Optional[str] = None
    voiceprint_threshold: Optional[float] = None
    # Sherpa-ONNX ASR configuration
    sherpa_model_dir: Optional[str] = None
    # KWS configuration
    sherpa_kws_enabled: Optional[bool] = None
    sherpa_kws_model_dir: Optional[str] = None
    sherpa_keywords: Optional[list[str]] = None


@config_router.put("")
async def update_config(update: ConfigUpdate):
    """Update configuration and persist to config.json."""
    global _current_config
    if not _current_config:
        _current_config = VoiceTypeConfig()

    current = _current_config.model_dump()
    updates = update.model_dump(exclude_none=True)

    # Don't overwrite keys with masked values
    for key in ("asr_api_key", "asr_secret_key", "llm_api_key"):
        if key in updates and "..." in updates[key]:
            del updates[key]
    
    # 如果前端删除了 API Keys（使用 Keyring），保留当前配置中的值
    # 这样热重载时才能正确判断是否启用 LLM/云 ASR
    if "asr_api_key" not in updates and current.get("asr_api_key"):
        pass  # Keep existing
    if "asr_secret_key" not in updates and current.get("asr_secret_key"):
        pass  # Keep existing
    if "llm_api_key" not in updates and current.get("llm_api_key"):
        pass  # Keep existing

    current.update(updates)
    _current_config = VoiceTypeConfig(**current)
    save_config(_current_config)

    logger.info("Config updated: %s", list(updates.keys()))
    
    # Hot reload LLM config if changed
    llm_changed = any(k in updates for k in ("llm_api_key", "llm_base_url", "llm_model"))
    if llm_changed and _engine_instance:
        try:
            _engine_instance.reload_llm_config(
                llm_api_key=_current_config.llm_api_key,
                llm_base_url=_current_config.llm_base_url,
                llm_model=_current_config.llm_model
            )
            logger.info("Triggered LLM config hot reload")
        except Exception as e:
            logger.error(f"Failed to trigger LLM hot reload: {e}")
    
    # Hot reload ASR config if changed
    asr_changed = any(k in updates for k in ("asr_provider", "asr_api_key", "asr_secret_key", "asr_model", 
                                               "asr_max_silence_ms", "asr_vad_threshold", "sherpa_model_dir"))
    if asr_changed and _engine_instance:
        try:
            _engine_instance.reload_asr_config(
                asr_provider=_current_config.asr_provider,
                asr_api_key=_current_config.asr_api_key,
                asr_secret_key=_current_config.asr_secret_key,
                asr_model=_current_config.asr_model,
                asr_max_silence_ms=_current_config.asr_max_silence_ms,
                asr_vad_threshold=_current_config.asr_vad_threshold,
                sherpa_model_dir=_current_config.sherpa_model_dir
            )
            logger.info("Triggered ASR config hot reload")
        except Exception as e:
            logger.error(f"Failed to trigger ASR hot reload: {e}")
    
    # Hot reload KWS keywords if changed
    kws_changed = "sherpa_kws_enabled" in updates or "sherpa_keywords" in updates or "sherpa_kws_model_dir" in updates
    if kws_changed and _engine_instance:
        try:
            import asyncio
            # 如果 KWS 启用状态改变，需要完整地启用/禁用 KWS
            if "sherpa_kws_enabled" in updates:
                if _current_config.sherpa_kws_enabled:
                    # 启用 KWS
                    asyncio.create_task(_engine_instance.enable_kws(
                        sherpa_kws_model_dir=_current_config.sherpa_kws_model_dir,
                        sherpa_keywords=_current_config.sherpa_keywords
                    ))
                    logger.info("Triggered KWS enable")
                else:
                    # 禁用 KWS
                    asyncio.create_task(_engine_instance.disable_kws())
                    logger.info("Triggered KWS disable")
            elif "sherpa_keywords" in updates or "sherpa_kws_model_dir" in updates:
                # 只是更新关键词或模型目录（KWS 保持启用状态）
                asyncio.create_task(_engine_instance.reload_kws_keywords(_current_config.sherpa_keywords))
                logger.info(f"Triggered KWS keywords hot reload: {_current_config.sherpa_keywords}")
        except Exception as e:
            logger.error(f"Failed to trigger KWS hot reload: {e}")
    
    return {"status": "ok", "updated": list(updates.keys())}


@config_router.post("/test")
async def test_connection():
    """Test LLM API connectivity with real request."""
    if not _current_config:
        return {"status": "error", "message": "配置未加载"}

    results = {}

    # Test LLM with real API call
    if _current_config.llm_api_key:
        try:
            from openai import AsyncOpenAI
            import asyncio
            
            client = AsyncOpenAI(
                api_key=_current_config.llm_api_key,
                base_url=_current_config.llm_base_url,
                timeout=10.0,  # 10s timeout
            )
            
            # Real LLM test: send a minimal request
            resp = await client.chat.completions.create(
                model=_current_config.llm_model,
                messages=[{"role": "user", "content": "测试"}],
                max_tokens=5,
            )
            
            await client.close()
            
            results["llm"] = {
                "status": "ok",
                "model": _current_config.llm_model,
                "message": f"连接正常 (模型: {_current_config.llm_model})"
            }
            logger.info("LLM connection test passed")
            
        except Exception as e:
            error_msg = str(e)
            # Parse common errors
            if "401" in error_msg or "Unauthorized" in error_msg:
                error_msg = "API Key 无效或已过期"
            elif "timeout" in error_msg.lower():
                error_msg = "连接超时，请检查网络"
            elif "model" in error_msg.lower():
                error_msg = f"模型 '{_current_config.llm_model}' 不可用"
            
            results["llm"] = {
                "status": "error",
                "message": error_msg
            }
            logger.warning(f"LLM connection test failed: {e}")
    else:
        results["llm"] = {
            "status": "error",
            "message": "未配置 LLM API Key"
        }

    # ASR status (simplified check)
    if _current_config.asr_provider == "sherpa":
        results["asr"] = {
            "status": "ok",
            "provider": "sherpa",
            "message": "本地 ASR (无需 API Key)"
        }
    elif _current_config.asr_api_key:
        results["asr"] = {
            "status": "ok",
            "provider": _current_config.asr_provider,
            "model": _current_config.asr_model,
            "message": f"{_current_config.asr_provider.title()} ASR 已配置"
        }
    else:
        results["asr"] = {
            "status": "error",
            "message": "未配置 ASR API Key"
        }

    return results
