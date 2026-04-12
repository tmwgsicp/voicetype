#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Aliyun speaker verification service.
阿里云说话人识别服务。

文档: https://help.aliyun.com/zh/isi/developer-reference/sdk-reference-4
"""

import asyncio
import json
import logging
import uuid
import websockets
from typing import Optional

from .base import BaseVoiceprintService, VoiceprintResult, VoiceprintProvider

logger = logging.getLogger(__name__)


class AliyunVoiceprintService(BaseVoiceprintService):
    """
    阿里云说话人识别服务。
    
    Features:
    - WebSocket 实时通信
    - 数字串验证机制
    - 高准确率识别
    """
    
    def __init__(self, appkey: str, token: str = None, access_key_id: str = None, access_key_secret: str = None, use_internal: bool = False):
        """
        初始化阿里云声纹服务。
        
        Args:
            appkey: 阿里云 Appkey
            token: 阿里云访问 Token（可选，如果提供 AccessKey 会自动获取）
            access_key_id: AccessKey ID（用于自动获取 Token）
            access_key_secret: AccessKey Secret（用于自动获取 Token）
            use_internal: 是否使用内网地址（仅阿里云 ECS）
        """
        self.appkey = appkey
        self.token = token
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        
        if use_internal:
            self.ws_url = "ws://nls-gateway-cn-shanghai-internal.aliyuncs.com:80/ws/v1"
        else:
            self.ws_url = "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1"
        
        # 如果没有提供 token，使用 AccessKey 自动获取
        if not self.token and self.access_key_id and self.access_key_secret:
            self._auto_refresh_token()
        
        logger.info(f"AliyunVoiceprintService initialized (appkey={'***' if appkey else 'None'}, token={'***' if self.token else 'None'})")
    
    def get_provider_name(self) -> str:
        return "阿里云"
    
    def is_available(self) -> bool:
        return bool(self.appkey and (self.token or (self.access_key_id and self.access_key_secret)))
    
    def _auto_refresh_token(self):
        """自动获取 Token"""
        try:
            from .aliyun_token import get_aliyun_nls_token
            
            logger.info("Auto-refreshing Aliyun NLS token...")
            token = get_aliyun_nls_token(self.access_key_id, self.access_key_secret)
            if token:
                self.token = token
                logger.info("Token auto-refreshed successfully")
            else:
                logger.error("Failed to auto-refresh token")
        except Exception as e:
            logger.error(f"Error auto-refreshing token: {e}")
    
    async def apply_digit(self, speaker_id: str) -> Optional[str]:
        """获取数字串"""
        try:
            # WebSocket URL 需要包含 token 参数
            ws_url_with_token = f"{self.ws_url}?token={self.token}"
            
            async with websockets.connect(ws_url_with_token, ping_interval=8, ping_timeout=30) as ws:
                # 生成消息 ID（不带连字符的32位十六进制）
                message_id = uuid.uuid4().hex
                task_id = uuid.uuid4().hex
                
                # 发送请求（按照官方文档格式）
                request = {
                    "header": {
                        "message_id": message_id,
                        "task_id": task_id,
                        "namespace": "SpeakerVerification",
                        "name": "StartTask",
                        "appkey": self.appkey
                    },
                    "payload": {
                        "action": "ApplyDigit",
                        "speaker_id": speaker_id
                    }
                }
                
                logger.debug(f"Sending request: {json.dumps(request)}")
                await ws.send(json.dumps(request))
                
                # 接收多个响应，直到获取到 TaskResult
                while True:
                    response = await ws.recv()
                    data = json.loads(response)
                    
                    logger.info(f"Received response: {data}")
                    
                    name = data.get("header", {}).get("name")
                    status = data.get("header", {}).get("status")
                    
                    if name == "TaskStarted":
                        # 任务开始，继续等待结果
                        logger.debug("Task started, waiting for result...")
                        continue
                    
                    elif name == "TaskResult":
                        # 任务结果
                        if status == 20000000:
                            digit = data.get("payload", {}).get("digit")
                            logger.info(f"Applied digit for {speaker_id}: {digit}")
                            return digit
                        else:
                            logger.error(f"Task failed: {data}")
                            return None
                    
                    elif name == "TaskFailed":
                        logger.error(f"Task failed: {data}")
                        return None
                    
                    else:
                        logger.warning(f"Unknown message type: {name}")
                    
        except Exception as e:
            logger.error(f"Error applying digit: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def enroll(
        self, 
        speaker_id: str, 
        audio: bytes, 
        digit: Optional[str] = None
    ) -> VoiceprintResult:
        """注册声纹"""
        if not digit:
            return VoiceprintResult(
                success=False,
                score=0.0,
                decision=False,
                message="需要数字串",
                provider=self.get_provider_name()
            )
        
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            async with websockets.connect(self.ws_url, extra_headers=headers) as ws:
                # 发送注册请求
                request = {
                    "header": {
                        "message_id": str(uuid.uuid4()),
                        "task_id": str(uuid.uuid4()),
                        "namespace": "SpeakerVerification",
                        "name": "StartTask",
                        "appkey": self.appkey
                    },
                    "payload": {
                        "action": "Enroll",
                        "format": "pcm",
                        "sample_rate": 16000,
                        "speaker_id": speaker_id,
                        "digit": digit
                    }
                }
                
                await ws.send(json.dumps(request))
                
                # 发送音频数据
                await ws.send(audio)
                
                # 接收结果
                response = await ws.recv()
                data = json.loads(response)
                
                status = data.get("header", {}).get("status")
                success = status == 20000000
                
                logger.info(f"Enroll result for {speaker_id}: {success}")
                
                return VoiceprintResult(
                    success=success,
                    score=100.0 if success else 0.0,
                    decision=success,
                    message=data.get("header", {}).get("status_text", ""),
                    provider=self.get_provider_name()
                )
                
        except Exception as e:
            logger.error(f"Error enrolling voiceprint: {e}")
            return VoiceprintResult(
                success=False,
                score=0.0,
                decision=False,
                message=str(e),
                provider=self.get_provider_name()
            )
    
    async def verify(
        self, 
        speaker_id: str, 
        audio: bytes, 
        digit: Optional[str] = None
    ) -> VoiceprintResult:
        """验证声纹"""
        if not digit:
            return VoiceprintResult(
                success=False,
                score=0.0,
                decision=False,
                message="需要数字串",
                provider=self.get_provider_name()
            )
        
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            async with websockets.connect(self.ws_url, extra_headers=headers) as ws:
                # 发送验证请求
                request = {
                    "header": {
                        "message_id": str(uuid.uuid4()),
                        "task_id": str(uuid.uuid4()),
                        "namespace": "SpeakerVerification",
                        "name": "StartTask",
                        "appkey": self.appkey
                    },
                    "payload": {
                        "action": "Verify",
                        "format": "pcm",
                        "sample_rate": 16000,
                        "speaker_id": speaker_id,
                        "digit": digit
                    }
                }
                
                await ws.send(json.dumps(request))
                
                # 发送音频数据
                await ws.send(audio)
                
                # 接收结果
                response = await ws.recv()
                data = json.loads(response)
                
                payload = data.get("payload", {})
                score = float(payload.get("score", 0.0))
                decision = payload.get("decision", 0) == 1
                
                logger.info(f"Verify result for {speaker_id}: score={score}, decision={decision}")
                
                return VoiceprintResult(
                    success=True,
                    score=score,
                    decision=decision,
                    message=data.get("header", {}).get("status_text", ""),
                    provider=self.get_provider_name()
                )
                
        except Exception as e:
            logger.error(f"Error verifying voiceprint: {e}")
            return VoiceprintResult(
                success=False,
                score=0.0,
                decision=False,
                message=str(e),
                provider=self.get_provider_name()
            )
    
    async def update(
        self, 
        speaker_id: str, 
        audio: bytes, 
        digit: Optional[str] = None
    ) -> VoiceprintResult:
        """更新声纹"""
        if not digit:
            return VoiceprintResult(
                success=False,
                score=0.0,
                decision=False,
                message="需要数字串",
                provider=self.get_provider_name()
            )
        
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            async with websockets.connect(self.ws_url, extra_headers=headers) as ws:
                # 发送更新请求
                request = {
                    "header": {
                        "message_id": str(uuid.uuid4()),
                        "task_id": str(uuid.uuid4()),
                        "namespace": "SpeakerVerification",
                        "name": "StartTask",
                        "appkey": self.appkey
                    },
                    "payload": {
                        "action": "Update",
                        "format": "pcm",
                        "sample_rate": 16000,
                        "speaker_id": speaker_id,
                        "digit": digit
                    }
                }
                
                await ws.send(json.dumps(request))
                
                # 发送音频数据
                await ws.send(audio)
                
                # 接收结果
                response = await ws.recv()
                data = json.loads(response)
                
                status = data.get("header", {}).get("status")
                success = status == 20000000
                
                logger.info(f"Update result for {speaker_id}: {success}")
                
                return VoiceprintResult(
                    success=success,
                    score=100.0 if success else 0.0,
                    decision=success,
                    message=data.get("header", {}).get("status_text", ""),
                    provider=self.get_provider_name()
                )
                
        except Exception as e:
            logger.error(f"Error updating voiceprint: {e}")
            return VoiceprintResult(
                success=False,
                score=0.0,
                decision=False,
                message=str(e),
                provider=self.get_provider_name()
            )
    
    async def delete(self, speaker_id: str) -> VoiceprintResult:
        """删除声纹"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            async with websockets.connect(self.ws_url, extra_headers=headers) as ws:
                # 发送删除请求
                request = {
                    "header": {
                        "message_id": str(uuid.uuid4()),
                        "task_id": str(uuid.uuid4()),
                        "namespace": "SpeakerVerification",
                        "name": "StartTask",
                        "appkey": self.appkey
                    },
                    "payload": {
                        "action": "Delete",
                        "speaker_id": speaker_id
                    }
                }
                
                await ws.send(json.dumps(request))
                
                # 接收结果
                response = await ws.recv()
                data = json.loads(response)
                
                status = data.get("header", {}).get("status")
                success = status == 20000000
                
                logger.info(f"Delete result for {speaker_id}: {success}")
                
                return VoiceprintResult(
                    success=success,
                    score=100.0 if success else 0.0,
                    decision=success,
                    message=data.get("header", {}).get("status_text", ""),
                    provider=self.get_provider_name()
                )
                
        except Exception as e:
            logger.error(f"Error deleting voiceprint: {e}")
            return VoiceprintResult(
                success=False,
                score=0.0,
                decision=False,
                message=str(e),
                provider=self.get_provider_name()
            )
