#!/usr/bin/env python3
# Copyright (C) 2026 VoiceForge Contributors
# Licensed under AGPL-3.0

"""
Extension configuration models with runtime validation.
Extension 配置模型，支持运行时验证。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator


class PortType(Enum):
    """端口数据类型"""
    AUDIO_FRAME = "audio_frame"
    TEXT = "text"
    TEXT_STREAM = "text_stream"
    COMMAND = "command"
    ANY = "any"


class PortConfig(BaseModel):
    """端口配置"""
    name: str = Field(..., description="端口名称", min_length=1, max_length=50)
    type: PortType = Field(..., description="数据类型")
    description: str = Field(default="", description="端口描述")
    required: bool = Field(default=True, description="是否必需")

    class Config:
        use_enum_values = True


class ExtensionConfig(BaseModel):
    """Extension 基础配置"""
    name: str = Field(..., min_length=1, max_length=100, description="扩展名称")
    version: str = Field(default="0.1.0", description="版本号")
    category: str = Field(default="general", description="分类")
    description: str = Field(default="", description="扩展描述")
    
    timeout: float = Field(default=30.0, gt=0, description="超时时间（秒）")
    retry_count: int = Field(default=0, ge=0, le=5, description="重试次数")
    
    input_ports: List[PortConfig] = Field(default_factory=list, description="输入端口")
    output_ports: List[PortConfig] = Field(default_factory=list, description="输出端口")
    
    custom_config: Dict[str, Any] = Field(default_factory=dict, description="自定义配置")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证名称格式"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('名称只能包含字母、数字、下划线和连字符')
        return v

    class Config:
        use_enum_values = True


class ASRConfig(ExtensionConfig):
    """ASR Extension 配置"""
    api_key: str = Field(default="", description="API Key (本地模式可留空)")
    model: str = Field(default="qwen3-asr-flash-realtime", description="模型名称")
    max_silence_ms: int = Field(default=1200, ge=200, le=10000, description="最大静音时长（毫秒）")
    vad_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="VAD 灵敏度阈值 (0.0-1.0)")
    sample_rate: int = Field(default=16000, description="采样率")
    language: str = Field(default="zh", description="语言代码")
