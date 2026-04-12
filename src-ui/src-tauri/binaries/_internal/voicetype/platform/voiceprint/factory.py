#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Voiceprint service factory.
声纹识别服务工厂。
"""

import logging
from typing import Optional

from .base import BaseVoiceprintService, VoiceprintProvider
from .aliyun_service import AliyunVoiceprintService

logger = logging.getLogger(__name__)


class VoiceprintServiceFactory:
    """
    声纹识别服务工厂。
    
    根据配置创建相应的声纹服务实例。
    """
    
    @staticmethod
    def create_service(
        provider: VoiceprintProvider,
        config: dict
    ) -> Optional[BaseVoiceprintService]:
        """
        创建声纹识别服务实例。
        
        Args:
            provider: 提供商类型
            config: 配置字典
        
        Returns:
            BaseVoiceprintService 实例，如果创建失败返回 None
        """
        try:
            if provider == VoiceprintProvider.ALIYUN:
                appkey = config.get("appkey")
                token = config.get("token")
                access_key_id = config.get("access_key_id")
                access_key_secret = config.get("access_key_secret")
                use_internal = config.get("use_internal", False)
                
                # Appkey 可以手动配置，也可以自动从控制台获取（需要手动在控制台创建项目）
                # Token 可以通过 AccessKey 自动获取
                if not appkey:
                    logger.warning("Aliyun appkey not provided. Please set it in config or .env")
                    logger.info("How to get appkey: https://nls-portal.console.aliyun.com/applist")
                
                if not token and not (access_key_id and access_key_secret):
                    logger.error("Aliyun config incomplete: need token or (access_key_id + access_key_secret)")
                    return None
                
                service = AliyunVoiceprintService(
                    appkey=appkey or "",
                    token=token,
                    access_key_id=access_key_id,
                    access_key_secret=access_key_secret,
                    use_internal=use_internal
                )
                logger.info(f"Created {service.get_provider_name()} voiceprint service")
                return service
            
            elif provider == VoiceprintProvider.TENCENT:
                logger.warning("Tencent voiceprint service not implemented yet")
                return None
            
            elif provider == VoiceprintProvider.IFLYTEK:
                logger.warning("Iflytek voiceprint service not implemented yet")
                return None
            
            elif provider == VoiceprintProvider.LOCAL_ONNX:
                from .local_service import LocalVoiceprintService
                from ...utils.path_helper import resolve_model_path
                
                model_path = config.get("model_path", "models/speaker_recognition.onnx")
                storage_dir = config.get("storage_dir", "data/voiceprints")
                
                # 解析模型路径
                model_path = resolve_model_path(model_path)
                storage_dir = resolve_model_path(storage_dir)
                
                sample_rate = config.get("sample_rate", 16000)
                threshold = config.get("threshold", 0.5)
                
                service = LocalVoiceprintService(
                    model_path=model_path,
                    storage_dir=storage_dir,
                    sample_rate=sample_rate,
                    threshold=threshold
                )
                logger.info(f"Created {service.get_provider_name()} voiceprint service")
                return service
            
            else:
                logger.error(f"Unknown provider: {provider}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create voiceprint service: {e}")
            return None
    
    @staticmethod
    def create_from_config(global_config: dict) -> Optional[BaseVoiceprintService]:
        """
        从全局配置创建声纹服务。
        
        Args:
            global_config: 全局配置字典
        
        Returns:
            BaseVoiceprintService 实例或 None
        """
        voiceprint_config = global_config.get("voiceprint", {})
        
        if not voiceprint_config.get("enabled", False):
            logger.info("Voiceprint feature is disabled")
            return None
        
        provider_str = voiceprint_config.get("provider", "aliyun")
        
        try:
            provider = VoiceprintProvider(provider_str)
        except ValueError:
            logger.error(f"Invalid voiceprint provider: {provider_str}")
            return None
        
        # 获取对应提供商的配置
        provider_config = voiceprint_config.get(provider_str, {})
        
        return VoiceprintServiceFactory.create_service(provider, provider_config)
