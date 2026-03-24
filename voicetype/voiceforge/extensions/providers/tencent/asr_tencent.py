#!/usr/bin/env python3
# Copyright (C) 2026 VoiceForge Contributors
# Licensed under AGPL-3.0

"""
Tencent Cloud ASR real-time speech recognition extension.
腾讯云实时语音识别扩展。

API Doc: https://cloud.tencent.com/document/product/1093/48982
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any, Optional, Union
from urllib.parse import urlencode

import websockets
from websockets.client import WebSocketClientProtocol

from voicetype.voiceforge.core.extension import ExtensionMeta, Port, PortType
from voicetype.voiceforge.core.config import ASRConfig
from voicetype.voiceforge.extensions.base_asr import BaseASRExtension

logger = logging.getLogger(__name__)

TENCENT_ASR_WS_BASE = "wss://asr.cloud.tencent.com/asr/v2/"


class TencentASRExtension(BaseASRExtension):
    """
    Tencent Cloud real-time speech recognition extension.
    腾讯云实时语音识别扩展。
    
    Features:
    - Real-time streaming recognition via WebSocket
    - Built-in VAD (Voice Activity Detection) 
    - Supports 16kHz PCM audio
    - Chinese and English recognition
    - Automatic punctuation and text filtering
    
    Configuration:
    - api_key: Tencent Cloud SecretId
    - secret_key: Tencent Cloud SecretKey (in config.custom_config)
    - model: Engine model type (default: "16k_zh")
    - max_silence_ms: VAD silence duration (default: 1200ms)
    """

    config_class = ASRConfig

    metadata = ExtensionMeta(
        name="tencent_asr",
        description="Tencent Cloud ASR with VAD support",
        category="asr",
    )
    input_ports = [
        Port("audio_frame", PortType.AUDIO_FRAME, "PCM 16kHz audio frame"),
    ]
    output_ports = [
        Port("text", PortType.TEXT, "Final recognition text"),
        Port("partial_text", PortType.TEXT, "Intermediate result", required=False),
    ]

    def __init__(
        self,
        config: Union[ASRConfig, dict[str, Any], None] = None,
    ):
        super().__init__(config)

        # Extract credentials
        self._secret_id: str = self.config.api_key or ""
        # SecretKey should be in config custom_config
        self._secret_key: str = self.config.custom_config.get("secret_key", "")
        
        if not self._secret_id or not self._secret_key:
            raise ValueError("Tencent ASR requires both SecretId (api_key) and SecretKey (secret_key)")
        
        # ASR parameters
        self._engine_model_type: str = self.config.model or "16k_zh"
        self._sample_rate: int = self.config.sample_rate
        self._language: str = self.config.language
        
        # VAD parameters (ms)
        self._vad_silence_time: int = self.config.max_silence_ms
        
        # Connection state
        self._ws: Optional[WebSocketClientProtocol] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._voice_id: str = ""
        self._seq: int = 0
        self._reconnect_lock = asyncio.Lock()

    def _generate_signature(self, params: dict) -> str:
        """
        Generate Tencent Cloud API signature.
        生成腾讯云 API 签名 (HMAC-SHA1)。
        """
        # Sort parameters by key
        sorted_params = sorted(params.items())
        query_string = urlencode(sorted_params)
        
        # Create signature base string
        sign_str = f"GET/asr/v2/{self._secret_id}?{query_string}"
        
        # Generate HMAC-SHA1 signature
        signature = hmac.new(
            self._secret_key.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha1
        ).digest()
        
        # Base64 encode
        return base64.b64encode(signature).decode('utf-8')

    async def establish_connection(self):
        """Establish WebSocket connection to Tencent ASR."""
        # Generate unique voice_id for this session
        self._voice_id = str(uuid.uuid4()).replace('-', '')
        timestamp = str(int(time.time()))
        expired = str(int(time.time()) + 3600)  # 1 hour expiration
        
        # Build query parameters
        params = {
            "secretid": self._secret_id,
            "timestamp": timestamp,
            "expired": expired,
            "nonce": str(uuid.uuid4().int)[:10],
            "engine_model_type": self._engine_model_type,
            "voice_id": self._voice_id,
            "voice_format": "1",  # 1=PCM
            "needvad": "1",  # Enable VAD
            "vad_silence_time": str(self._vad_silence_time),
            "filter_dirty": "1",  # Filter profanity
            "filter_modal": "1",  # Filter filler words (um, uh)
            "filter_punc": "0",  # Keep punctuation
            "convert_num_mode": "1",  # Convert numbers
        }
        
        # Generate signature
        signature = self._generate_signature(params)
        params["signature"] = signature
        
        # Build WebSocket URL
        url = TENCENT_ASR_WS_BASE + self._secret_id + "?" + urlencode(params)
        
        try:
            self._ws = await websockets.connect(
                url,
                max_size=None,
                ping_interval=20,
                ping_timeout=10,
            )
            logger.info(
                "[%s] Connected to Tencent ASR: %s (voice_id=%s, vad=%dms)",
                self.config.name, self._engine_model_type, 
                self._voice_id[:8], self._vad_silence_time
            )
            
            # Start receive loop
            self._recv_task = asyncio.create_task(self._receive_loop())
            self._tasks.append(self._recv_task)
            
        except Exception as e:
            logger.error("[%s] Failed to connect Tencent ASR: %s", self.config.name, e)
            raise ConnectionError(f"Tencent ASR connection failed: {e}")

    async def _do_start(self):
        await self.establish_connection()

    async def send_audio(self, audio_data: bytes):
        """Send audio chunk to Tencent ASR."""
        if not self._ws:
            logger.error("[%s] WebSocket not connected", self.config.name)
            return

        try:
            # Encode audio to base64
            encoded = base64.b64encode(audio_data).decode("ascii")
            
            # Build data packet
            packet = {
                "voice_id": self._voice_id,
                "seq": self._seq,
                "end": 0,  # 0=continue, 1=end
                "voice_format": 1,  # 1=PCM
                "data": encoded,
            }
            
            await self._ws.send(json.dumps(packet))
            self._seq += 1
            
        except Exception as e:
            logger.error("[%s] Failed to send audio: %s", self.config.name, e)
            # Attempt reconnection
            await self._reconnect()

    async def _send_end_signal(self):
        """Send end signal to finish the current recognition session."""
        if not self._ws:
            return
            
        try:
            packet = {
                "voice_id": self._voice_id,
                "seq": self._seq,
                "end": 1,  # End signal
                "voice_format": 1,
                "data": "",
            }
            await self._ws.send(json.dumps(packet))
            logger.debug("[%s] Sent end signal", self.config.name)
        except Exception as e:
            logger.warning("[%s] Failed to send end signal: %s", self.config.name, e)

    async def _reconnect(self) -> bool:
        """Reconnect to Tencent ASR service."""
        async with self._reconnect_lock:
            try:
                if self._ws:
                    try:
                        await self._ws.close()
                    except Exception:
                        pass

                logger.info("[%s] Reconnecting Tencent ASR...", self.config.name)
                await self.establish_connection()
                self._seq = 0  # Reset sequence number
                logger.info("[%s] Reconnection successful", self.config.name)
                return True
                
            except Exception as e:
                logger.error("[%s] Reconnection failed: %s", self.config.name, e)
                return False

    async def on_data(self, port: str, data: Any):
        """Handle incoming audio data."""
        if port == "audio_frame" and isinstance(data, bytes):
            if len(data) > 0:
                await self.send_audio(data)

    async def disconnect(self):
        """Close connection and cleanup resources."""
        # Send end signal
        await self._send_end_signal()
        # Give server time to process (reduced to 0.1s for better UX)
        await asyncio.sleep(0.1)
        
        # Cleanup tasks
        await self._cleanup_tasks()
        
        # Close WebSocket
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            logger.info("[%s] Tencent ASR disconnected", self.config.name)

    async def _do_stop(self):
        await self.disconnect()

    async def _cleanup_tasks(self):
        """Cancel background tasks."""
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass

    async def _receive_loop(self):
        """Receive and process ASR results from Tencent Cloud."""
        max_reconnects = 2
        
        for attempt in range(max_reconnects + 1):
            try:
                async for msg in self._ws:
                    # Decode message
                    if isinstance(msg, bytes):
                        msg = msg.decode('utf-8')
                    
                    try:
                        data = json.loads(msg)
                    except json.JSONDecodeError:
                        logger.warning("[%s] Invalid JSON: %s", self.config.name, msg[:100])
                        continue
                    
                    # Check response code
                    code = data.get("code")
                    if code != 0:
                        error_msg = data.get("message", "Unknown error")
                        logger.error(
                            "[%s] Tencent ASR error [code=%s]: %s",
                            self.config.name, code, error_msg
                        )
                        await self.send("error", f"ASR error: {error_msg}")
                        return
                    
                    # Parse recognition result
                    result = data.get("result", {})
                    slice_type = result.get("slice_type", 0)
                    voice_text_str = result.get("voice_text_str", "")
                    
                    if not voice_text_str:
                        continue
                    
                    # slice_type: 0=start, 1=partial, 2=end
                    if slice_type == 1:
                        # Intermediate result
                        await self.send("partial_text", voice_text_str.strip())
                        logger.debug("[%s] ASR partial: %s", self.config.name, voice_text_str.strip())
                        
                    elif slice_type == 2:
                        # Final result (sentence complete)
                        await self.send("text", voice_text_str.strip())
                        logger.info("[%s] ASR final: %s", self.config.name, voice_text_str.strip())
                
                # WebSocket closed normally
                return
                
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning("[%s] WebSocket closed: %s", self.config.name, e)
                if attempt < max_reconnects:
                    logger.info(
                        "[%s] Attempting reconnect (%d/%d)...",
                        self.config.name, attempt + 1, max_reconnects
                    )
                    ok = await self._reconnect()
                    if not ok:
                        logger.error("[%s] Reconnection failed", self.config.name)
                        await self.send("error", "ASR connection lost")
                        return
                else:
                    logger.error("[%s] Max reconnect attempts reached", self.config.name)
                    await self.send("error", "ASR connection lost after retries")
                    
            except asyncio.CancelledError:
                return
                
            except Exception as e:
                logger.error("[%s] Receive loop error: %s", self.config.name, e)
                await self.send("error", f"ASR error: {e}")
                return
