#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Base interface for voiceprint recognition services.
声纹识别服务基础接口。
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Tuple, Optional
from dataclasses import dataclass


class VoiceprintProvider(Enum):
    """声纹识别提供商"""
    ALIYUN = "aliyun"      # 阿里云说话人识别
    TENCENT = "tencent"    # 腾讯云说话人验证
    IFLYTEK = "iflytek"    # 科大讯飞声纹识别
    LOCAL_ONNX = "local"   # 本地 ONNX 模型


@dataclass
class VoiceprintResult:
    """声纹识别结果"""
    success: bool           # 是否成功
    score: float           # 置信度分数 (0-100)
    decision: bool         # 判决结果（通过/拒绝）
    message: str = ""      # 附加消息
    provider: str = ""     # 提供商名称


class BaseVoiceprintService(ABC):
    """
    声纹识别服务基类。
    
    所有云端和本地服务都实现此接口，确保统一的调用方式。
    """
    
    @abstractmethod
    async def apply_digit(self, speaker_id: str) -> Optional[str]:
        """
        获取验证数字串（云端需要，本地不需要）。
        
        Args:
            speaker_id: 说话人 ID
        
        Returns:
            数字串（如 "04587236"），本地模式返回 None
        """
        pass
    
    @abstractmethod
    async def enroll(
        self, 
        speaker_id: str, 
        audio: bytes, 
        digit: Optional[str] = None
    ) -> VoiceprintResult:
        """
        注册声纹。
        
        Args:
            speaker_id: 说话人 ID
            audio: 音频数据（PCM 16kHz 16bit mono）
            digit: 验证数字串（云端需要）
        
        Returns:
            VoiceprintResult 注册结果
        """
        pass
    
    @abstractmethod
    async def verify(
        self, 
        speaker_id: str, 
        audio: bytes, 
        digit: Optional[str] = None
    ) -> VoiceprintResult:
        """
        验证声纹。
        
        Args:
            speaker_id: 说话人 ID
            audio: 音频数据（PCM 16kHz 16bit mono）
            digit: 验证数字串（云端需要）
        
        Returns:
            VoiceprintResult 验证结果
        """
        pass
    
    @abstractmethod
    async def update(
        self, 
        speaker_id: str, 
        audio: bytes, 
        digit: Optional[str] = None
    ) -> VoiceprintResult:
        """
        更新声纹。
        
        Args:
            speaker_id: 说话人 ID
            audio: 音频数据（PCM 16kHz 16bit mono）
            digit: 验证数字串（云端需要）
        
        Returns:
            VoiceprintResult 更新结果
        """
        pass
    
    @abstractmethod
    async def delete(self, speaker_id: str) -> VoiceprintResult:
        """
        删除声纹。
        
        Args:
            speaker_id: 说话人 ID
        
        Returns:
            VoiceprintResult 删除结果
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """获取提供商名称"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查服务是否可用（配置是否完整）"""
        pass
