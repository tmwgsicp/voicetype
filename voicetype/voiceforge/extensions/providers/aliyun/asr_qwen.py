#!/usr/bin/env python3
# Copyright (C) 2026 VoiceForge Contributors
# Licensed under AGPL-3.0

"""
Aliyun Qwen3-ASR real-time speech recognition extension.
Uses OpenAI Realtime WebSocket protocol (different from DashScope inference protocol).
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from typing import Any, Optional, Union

import websockets
from websockets.client import WebSocketClientProtocol

from voicetype.voiceforge.core.extension import ExtensionMeta, Port, PortType
from voicetype.voiceforge.core.config import ASRConfig
from voicetype.voiceforge.extensions.base_asr import BaseASRExtension

logger = logging.getLogger(__name__)

QWEN_ASR_WS_BASE = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"


class QwenASRExtension(BaseASRExtension):
    """
    Aliyun Qwen3-ASR real-time speech recognition extension.
    Uses OpenAI Realtime WebSocket protocol with server-side VAD.
    """

    config_class = ASRConfig

    metadata = ExtensionMeta(
        name="qwen_asr",
        description="Aliyun Qwen3-ASR real-time speech recognition (OpenAI Realtime protocol)",
        category="asr",
    )
    input_ports = [
        Port("audio_frame", PortType.AUDIO_FRAME, "PCM 16kHz audio frame"),
    ]
    output_ports = [
        Port("text", PortType.TEXT, "Final recognition text"),
        Port("partial_text", PortType.TEXT, "Intermediate recognition result", required=False),
    ]

    def __init__(
        self,
        config: Union[ASRConfig, dict[str, Any], None] = None,
    ):
        super().__init__(config)

        self._api_key: str = self.config.api_key
        self._model: str = self.config.model
        self._max_silence_ms: int = self.config.max_silence_ms
        self._sample_rate: int = self.config.sample_rate
        self._language: str = self.config.language

        self._ws: Optional[WebSocketClientProtocol] = None
        self._session_configured = asyncio.Event()
        self._recv_task: Optional[asyncio.Task] = None
        self._reconnect_lock = asyncio.Lock()

    async def establish_connection(self):
        url = f"{QWEN_ASR_WS_BASE}?model={self._model}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "OpenAI-Beta": "realtime=v1",
        }
        self._ws = await websockets.connect(
            url,
            additional_headers=headers,
            max_size=None,
        )
        logger.info("[%s] Connected to Qwen ASR: %s", self.config.name, self._model)

        self._recv_task = asyncio.create_task(self._receive_loop())
        self._tasks.append(self._recv_task)

        await self._send_session_update()

        try:
            await asyncio.wait_for(self._session_configured.wait(), timeout=10.0)
            logger.info("[%s] Qwen ASR session configured", self.config.name)
        except asyncio.TimeoutError:
            logger.error("[%s] Qwen ASR session config timeout", self.config.name)
            await self._cleanup_tasks()
            if self._ws:
                await self._ws.close()
            raise ConnectionError("Qwen ASR session config timeout")

    async def _send_session_update(self):
        self._session_configured.clear()

        session_update = {
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "type": "session.update",
            "session": {
                "modalities": ["text"],
                "input_audio_format": "pcm",
                "sample_rate": self._sample_rate,
                "input_audio_transcription": {
                    "language": self._language,
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.0,  # 推荐值：提高VAD灵敏度
                    "silence_duration_ms": self._max_silence_ms,
                },
            },
        }
        await self._ws.send(json.dumps(session_update))
        logger.info(
            "[%s] Sent session.update (VAD mode, silence=%dms, lang=%s)",
            self.config.name, self._max_silence_ms, self._language,
        )

    async def _do_start(self):
        await self.establish_connection()

    async def send_audio(self, audio_data: bytes):
        if not self._ws:
            logger.error("[%s] WebSocket not connected, cannot send audio", self.config.name)
            return

        encoded = base64.b64encode(audio_data).decode("ascii")
        event = {
            "event_id": f"audio_{uuid.uuid4().hex[:8]}",
            "type": "input_audio_buffer.append",
            "audio": encoded,
        }

        success = await self._send_with_recovery(json.dumps(event), max_retries=1)
        if not success:
            logger.error("[%s] Failed to send audio chunk after retries", self.config.name)
    
    async def commit_audio(self):
        """
        手动提交音频缓冲区（Manual模式）
        通知服务端立即处理，不等VAD静音
        """
        if not self._ws:
            logger.warning("[%s] WebSocket not connected, cannot commit", self.config.name)
            return
        
        event = {
            "event_id": f"commit_{uuid.uuid4().hex[:8]}",
            "type": "input_audio_buffer.commit",
        }
        
        try:
            await self._ws.send(json.dumps(event))
            logger.info("[%s] Manual commit sent (bypass VAD wait)", self.config.name)
        except Exception as e:
            logger.error("[%s] Failed to send commit: %s", self.config.name, e)

    async def _send_with_recovery(self, data: str, max_retries: int = 1) -> bool:
        for attempt in range(max_retries + 1):
            try:
                await self._ws.send(data)
                return True
            except Exception as e:
                logger.warning(
                    "[%s] Send failed (attempt %d/%d): %s",
                    self.config.name, attempt + 1, max_retries + 1, e,
                )
                if attempt < max_retries:
                    reconnect_ok = await self._reconnect()
                    if not reconnect_ok:
                        return False
                    await asyncio.sleep(0.1)
                else:
                    return False
        return False

    async def _reconnect(self) -> bool:
        async with self._reconnect_lock:
            try:
                if self._ws:
                    try:
                        await self._ws.close()
                    except Exception:
                        pass

                logger.info("[%s] Reconnecting Qwen ASR...", self.config.name)
                url = f"{QWEN_ASR_WS_BASE}?model={self._model}"
                headers = {
                    "Authorization": f"Bearer {self._api_key}",
                    "OpenAI-Beta": "realtime=v1",
                }
                self._ws = await websockets.connect(
                    url,
                    additional_headers=headers,
                    max_size=None,
                )
                self._session_configured.clear()
                await self._send_session_update()
                await asyncio.wait_for(self._session_configured.wait(), timeout=5.0)
                logger.info("[%s] Reconnection successful", self.config.name)
                return True
            except Exception as e:
                logger.error("[%s] Reconnection failed: %s", self.config.name, e)
                return False

    async def on_data(self, port: str, data: Any):
        if port == "audio_frame" and isinstance(data, bytes):
            if len(data) == 0:
                return
            await self.send_audio(data)

    async def disconnect(self):
        if self._ws:
            try:
                finish_event = {
                    "event_id": f"fin_{uuid.uuid4().hex[:8]}",
                    "type": "session.finish",
                }
                await self._ws.send(json.dumps(finish_event))
                # Reduced delay for better UX (0.1s instead of 0.5s)
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.warning("[%s] Error sending session.finish: %s", self.config.name, e)

        await self._cleanup_tasks()

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            logger.info("[%s] Qwen ASR connection closed", self.config.name)

    async def _do_stop(self):
        await self.disconnect()

    async def _cleanup_tasks(self):
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass

    async def _receive_loop(self):
        max_reconnects = 2
        for attempt in range(max_reconnects + 1):
            try:
                async for msg in self._ws:
                    if isinstance(msg, bytes):
                        continue

                    data = json.loads(msg)
                    event_type = data.get("type", "")

                    if event_type == "session.created":
                        session_id = data.get("session", {}).get("id", "")
                        logger.info("[%s] Session created: %s", self.config.name, session_id)
                        self._session_configured.set()

                    elif event_type == "session.updated":
                        self._session_configured.set()
                        logger.info("[%s] Session updated/configured", self.config.name)

                    elif event_type == "input_audio_buffer.speech_started":
                        logger.debug("[%s] VAD: speech started", self.config.name)

                    elif event_type == "input_audio_buffer.speech_stopped":
                        logger.debug("[%s] VAD: speech stopped", self.config.name)

                    elif event_type == "conversation.item.input_audio_transcription.text":
                        # 根据官方文档，实时预览 = text（已确认）+ stash（草稿）
                        confirmed_text = data.get("text", "")
                        draft_text = data.get("stash", "")
                        full_text = (confirmed_text + draft_text).strip()
                        
                        if full_text:
                            await self.send("partial_text", full_text)
                            logger.debug("[%s] ASR partial: '%s' (text='%s', stash='%s')", 
                                        self.config.name, full_text, confirmed_text, draft_text)

                    elif event_type == "conversation.item.input_audio_transcription.completed":
                        transcript = data.get("transcript", "")
                        if transcript and transcript.strip():
                            await self.send("text", transcript.strip())
                            logger.info("[%s] ASR final: %s", self.config.name, transcript.strip())

                    elif event_type == "session.finished":
                        logger.info("[%s] Session finished", self.config.name)
                        return

                    elif event_type == "error":
                        error_msg = data.get("error", {}).get("message", str(data))
                        logger.error("[%s] Qwen ASR error: %s", self.config.name, error_msg)
                        return

                    else:
                        logger.debug("[%s] Unhandled event: %s", self.config.name, event_type)

                return

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning("[%s] Qwen ASR WebSocket closed unexpectedly: %s", self.config.name, e)
                if attempt < max_reconnects:
                    logger.info("[%s] Attempting receive-side reconnect (%d/%d)...", self.config.name, attempt + 1, max_reconnects)
                    ok = await self._reconnect()
                    if not ok:
                        logger.error("[%s] Receive-side reconnect failed, giving up", self.config.name)
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
