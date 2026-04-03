#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
API routes for voiceprint management.
声纹管理 API。
"""

import logging
import json
import base64
from typing import Optional, List
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import get_config_dir
from ..platform.voiceprint.factory import VoiceprintServiceFactory
from ..platform.voiceprint.base import VoiceprintProvider

logger = logging.getLogger(__name__)

voiceprint_router = APIRouter(prefix="/api/voiceprint", tags=["voiceprint"])

# 全局声纹服务实例
_voiceprint_service = None
_voiceprint_enabled = False
_engine_instance = None  # Engine 实例引用


def set_engine_instance(engine):
    """设置 Engine 实例（由 main.py 调用）"""
    global _engine_instance
    _engine_instance = engine


def get_voiceprint_service():
    """获取声纹服务实例"""
    global _voiceprint_service
    
    if _voiceprint_service is None:
        # 从配置创建服务
        config = {
            "model_path": "models/speaker_recognition.onnx",
            "storage_dir": str(get_config_dir() / "voiceprints"),
            "sample_rate": 16000,
            "threshold": 0.5
        }
        _voiceprint_service = VoiceprintServiceFactory.create_service(
            VoiceprintProvider.LOCAL_ONNX,
            config
        )
    
    return _voiceprint_service


class VoiceprintSettings(BaseModel):
    """声纹设置"""
    enabled: bool
    provider: str = "local"
    threshold: float = 0.5


class EnrollmentRequest(BaseModel):
    """注册声纹请求"""
    speaker_id: str = Field(..., description="用户 ID")
    audio_base64: str = Field(..., description="Base64 编码的音频数据（PCM 16-bit, 16kHz, mono）")


class VerificationRequest(BaseModel):
    """验证声纹请求"""
    speaker_id: str = Field(..., description="用户 ID")
    audio_base64: str = Field(..., description="Base64 编码的音频数据")


class VoiceprintInfo(BaseModel):
    """声纹信息"""
    speaker_id: str
    provider: str
    threshold: float
    created_at: str


@voiceprint_router.get("/settings")
async def get_settings():
    """获取声纹设置"""
    # 从配置文件读取持久化状态
    config_file = get_config_dir() / "voiceprint_settings.json"
    enabled = _voiceprint_enabled
    
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                saved_settings = json.load(f)
                enabled = saved_settings.get("enabled", False)
        except Exception as e:
            logger.error(f"Failed to load voiceprint settings: {e}")
    
    return {
        "enabled": enabled,
        "provider": "local",
        "threshold": 0.5
    }


@voiceprint_router.post("/settings/enable")
async def set_enabled(settings: VoiceprintSettings):
    """启用/禁用声纹识别"""
    global _voiceprint_enabled
    _voiceprint_enabled = settings.enabled
    
    # 持久化到配置文件
    config_file = get_config_dir() / "voiceprint_settings.json"
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump({
                "enabled": settings.enabled,
                "provider": "local",
                "threshold": 0.5
            }, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save voiceprint settings: {e}")
    
    # 同步更新 Engine 的状态
    if _engine_instance:
        _engine_instance.set_voiceprint_enabled(_voiceprint_enabled)
    
    logger.info(f"Voiceprint {'enabled' if _voiceprint_enabled else 'disabled'}")
    
    return {"success": True, "enabled": _voiceprint_enabled}


@voiceprint_router.post("/enroll")
async def enroll(req: EnrollmentRequest):
    """
    注册声纹。
    
    说明：
    - 接收 base64 编码的音频数据
    - 提取声纹特征向量（256维）
    - 保存向量到 JSON（约 2KB）
    - NO: 不保存原始录音文件
    """
    service = get_voiceprint_service()
    
    if not service:
        raise HTTPException(status_code=500, detail="声纹服务未初始化")
    
    try:
        # 解码 base64 音频
        audio_bytes = base64.b64decode(req.audio_base64)
        
        # 注册声纹（只保存向量，不保存录音）
        result = await service.enroll(req.speaker_id, audio_bytes)
        
        if result.success:
            return {
                "success": True,
                "message": result.message,
                "speaker_id": req.speaker_id
            }
        else:
            raise HTTPException(status_code=400, detail=result.message)
            
    except Exception as e:
        logger.error(f"Enrollment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@voiceprint_router.post("/verify")
async def verify(req: VerificationRequest):
    """
    验证声纹。
    
    说明：
    - 接收 base64 编码的音频数据
    - 提取声纹特征向量
    - 与已保存的向量对比
    - NO: 不保存任何数据
    """
    service = get_voiceprint_service()
    
    if not service:
        raise HTTPException(status_code=500, detail="声纹服务未初始化")
    
    try:
        # 解码 base64 音频
        audio_bytes = base64.b64decode(req.audio_base64)
        
        # 验证声纹（不保存任何数据）
        result = await service.verify(req.speaker_id, audio_bytes)
        
        return {
            "success": result.success,
            "decision": result.decision,
            "score": result.score,
            "message": result.message
        }
            
    except Exception as e:
        logger.error(f"Verification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@voiceprint_router.get("/list")
async def list_voiceprints():
    """列出所有已注册的声纹"""
    service = get_voiceprint_service()
    
    if not service:
        return {"voiceprints": [], "total": 0}
    
    # 扫描存储目录
    storage_dir = Path(get_config_dir() / "voiceprints")
    if not storage_dir.exists():
        return {"voiceprints": [], "total": 0}
    
    voiceprints = []
    for vp_file in storage_dir.glob("*.json"):
        try:
            with open(vp_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                voiceprints.append({
                    "speaker_id": data["speaker_id"],
                    "threshold": data.get("threshold", 0.5),
                    "provider": "本地 ONNX",
                    "embedding_size": len(data.get("embedding", [])),
                    "enrollment_rounds": data.get("enrollment_rounds", 1),
                    "created_at": vp_file.stat().st_ctime
                })
        except Exception as e:
            logger.error(f"Error reading voiceprint {vp_file}: {e}")
    
    return {
        "voiceprints": voiceprints,
        "total": len(voiceprints),
        "enabled": _voiceprint_enabled
    }


@voiceprint_router.delete("/{speaker_id}")
async def delete_voiceprint(speaker_id: str):
    """删除声纹"""
    service = get_voiceprint_service()
    
    if not service:
        raise HTTPException(status_code=500, detail="声纹服务未初始化")
    
    result = await service.delete(speaker_id)
    
    if result.success:
        return {"success": True, "message": result.message}
    else:
        raise HTTPException(status_code=404, detail=result.message)


@voiceprint_router.put("/{speaker_id}/threshold")
async def update_threshold(speaker_id: str, threshold: float):
    """更新声纹阈值"""
    storage_dir = Path(get_config_dir() / "voiceprints")
    vp_file = storage_dir / f"{speaker_id}.json"
    
    if not vp_file.exists():
        raise HTTPException(status_code=404, detail="声纹不存在")
    
    try:
        with open(vp_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        data["threshold"] = threshold
        
        with open(vp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        
        return {"success": True, "threshold": threshold}
        
    except Exception as e:
        logger.error(f"Error updating threshold: {e}")
        raise HTTPException(status_code=500, detail=str(e))
