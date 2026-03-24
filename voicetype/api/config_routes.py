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


def set_config(config: VoiceTypeConfig):
    global _current_config
    _current_config = config


class ConfigResponse(BaseModel):
    """Config response with masked API keys."""
    asr_provider: str
    asr_api_key: str
    asr_secret_key: str
    asr_model: str
    asr_max_silence_ms: int
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_temperature: float
    rag_enabled: bool
    qdrant_storage_path: str
    qdrant_collection: str
    rag_embedding_model: str
    rag_top_k: int
    rag_score_threshold: float
    hotkey: str
    typing_delay_ms: int
    host: str
    port: int
    auto_start_asr: bool


@config_router.get("", response_model=ConfigResponse)
async def get_config():
    """Get current configuration (API keys masked)."""
    if not _current_config:
        return ConfigResponse(**VoiceTypeConfig().model_dump())

    data = _current_config.model_dump()
    data["asr_api_key"] = mask_key(_current_config.asr_api_key)
    data["asr_secret_key"] = mask_key(_current_config.asr_secret_key)
    data["llm_api_key"] = mask_key(_current_config.llm_api_key)
    return ConfigResponse(**data)


class ConfigUpdate(BaseModel):
    asr_provider: Optional[str] = None
    asr_api_key: Optional[str] = None
    asr_secret_key: Optional[str] = None
    asr_model: Optional[str] = None
    asr_max_silence_ms: Optional[int] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    rag_enabled: Optional[bool] = None
    qdrant_storage_path: Optional[str] = None
    qdrant_collection: Optional[str] = None
    rag_embedding_model: Optional[str] = None
    rag_top_k: Optional[int] = None
    rag_score_threshold: Optional[float] = None
    hotkey: Optional[str] = None
    typing_delay_ms: Optional[int] = None
    auto_start_asr: Optional[bool] = None


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

    current.update(updates)
    _current_config = VoiceTypeConfig(**current)
    save_config(_current_config)

    logger.info("Config updated: %s", list(updates.keys()))
    return {"status": "ok", "updated": list(updates.keys())}


@config_router.post("/test")
async def test_connection():
    """Test API key connectivity."""
    if not _current_config:
        return {"status": "error", "message": "No config loaded"}

    results = {}

    # Test LLM
    if _current_config.llm_api_key:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=_current_config.llm_api_key,
                base_url=_current_config.llm_base_url,
            )
            resp = await client.chat.completions.create(
                model=_current_config.llm_model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            await client.close()
            results["llm"] = {"status": "ok", "model": _current_config.llm_model}
        except Exception as e:
            results["llm"] = {"status": "error", "message": str(e)}
    else:
        results["llm"] = {"status": "error", "message": "No API key"}

    results["asr"] = {
        "status": "ok" if _current_config.asr_api_key else "error",
        "model": _current_config.asr_model,
        "message": "" if _current_config.asr_api_key else "No API key",
    }

    return results
