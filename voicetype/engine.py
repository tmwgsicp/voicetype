#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
VoiceTypingEngine: the central coordinator that wires everything together.
Manages lifecycle of Microphone, ASR, RAG, WindowWatcher, SceneClassifier,
Pipeline, HotkeyListener, and KeyboardOutput.
"""

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import WebSocket

from .voiceforge.core.config import ASRConfig
from .voiceforge.extensions.base_asr import BaseASRExtension
from .voiceforge.extensions.providers.aliyun.asr_qwen import QwenASRExtension
from .voiceforge.extensions.providers.tencent.asr_tencent import TencentASRExtension
from .voiceforge.extensions.rag_local import RAGLocalExtension, RAGLocalConfig

_QWEN_ASR_MODELS = {
    "qwen3-asr-flash-realtime",
    "qwen3-asr-flash-realtime-2026-02-10",
    "qwen3-asr-flash-realtime-2025-10-27",
}

_TENCENT_ASR_MODELS = {
    "16k_zh",  # 16k 中文
    "16k_zh_video",  # 16k 音视频
    "16k_en",  # 16k 英文
    "16k_ca",  # 16k 粤语
}


def _task_done_callback(task: asyncio.Task):
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logging.getLogger(__name__).error("Background task %s failed: %s", task.get_name(), exc)

from .platform.microphone import Microphone
from .platform.window_watcher import WindowWatcher, WindowInfo
from .context.scene_classifier import SceneClassifier, Scene, SCENES
from .pipeline.voice_pipeline import VoiceTypingPipeline
from .platform.keyboard_output import KeyboardOutput
from .platform.hotkey_listener import HotkeyListener

logger = logging.getLogger(__name__)

RAG_TIMEOUT_S = 1.0


class VoiceTypingEngine:
    """Central engine coordinating all voice typing components."""

    def __init__(
        self,
        llm_api_key: str,
        llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        llm_model: str = "qwen-turbo-latest",
        asr_provider: str = "aliyun",
        asr_api_key: str = "",
        asr_secret_key: str = "",  # For Tencent Cloud
        asr_model: str = "qwen3-asr-flash-realtime",
        asr_max_silence_ms: int = 1200,
        hotkey: str = "<ctrl>+<shift>+v",
        typing_delay_ms: int = 5,
        rag_enabled: bool = False,
        rag_embedding_model: str = "BAAI/bge-small-zh-v1.5",
        rag_qdrant_url: str = "localhost",
        rag_qdrant_port: int = 6333,
        rag_qdrant_collection: str = "voicetype-kb",
        rag_top_k: int = 3,
        rag_score_threshold: float = 0.5,
    ):
        self._asr_provider = asr_provider
        self._asr_api_key = asr_api_key
        self._asr_secret_key = asr_secret_key
        self._asr_model = asr_model
        self._asr_max_silence_ms = asr_max_silence_ms
        self._asr_ext: Optional[BaseASRExtension] = None

        self._microphone = Microphone()

        self._rag_enabled = rag_enabled
        self._rag_ext: Optional[RAGLocalExtension] = None
        if rag_enabled:
            rag_config = {
                "name": "voice_typing_rag",
                "embedding_model": rag_embedding_model,
                "qdrant_collection_name": rag_qdrant_collection,
                "top_k": rag_top_k,
                "score_threshold": rag_score_threshold,
            }
            rag_config["qdrant_url"] = rag_qdrant_url
            rag_config["qdrant_port"] = rag_qdrant_port
            self._rag_ext = RAGLocalExtension(rag_config)

        self.pipeline = VoiceTypingPipeline(
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
        )

        self.window_watcher = WindowWatcher(poll_interval_ms=200)
        self.scene_classifier = SceneClassifier()

        self.keyboard_output = KeyboardOutput(typing_delay_ms=typing_delay_ms)
        self.hotkey_listener = HotkeyListener(
            hotkey=hotkey,
            on_activate=self.start_recording,
            on_deactivate=self.stop_recording,
            is_active_fn=lambda: self._is_recording,
        )

        self._is_recording = False
        self._recording_lock = asyncio.Lock()
        self._last_toggle_time = 0.0  # For debounce/cooldown
        self._toggle_cooldown = 0.3  # 300ms cooldown between toggles
        self._scene_override: Optional[str] = None
        self._ws_clients: list[WebSocket] = []

        self.window_watcher.on_change(self._on_window_change)
        self.pipeline.on_raw_text(self._on_raw_text)
        self.pipeline.on_final_text_stream(self._on_final_text_stream)
        self.pipeline.on_final_text(self._on_final_complete)

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def set_scene_override(self, scene_name: Optional[str]):
        if scene_name and scene_name in SCENES:
            self._scene_override = scene_name
            self.pipeline.set_scene(SCENES[scene_name])
            logger.info("Scene override: %s", scene_name)
        else:
            self._scene_override = None
            logger.info("Scene override cleared, back to auto-detection")

    async def start(self):
        """Initialize all components."""
        await self.keyboard_output.start()
        await self.window_watcher.start()
        await self.hotkey_listener.start()

        if self._rag_ext:
            try:
                await self._rag_ext.on_start()
                logger.info("RAG knowledge base ready")
            except Exception as e:
                logger.warning("RAG initialization failed, continuing without: %s", e)
                self._rag_ext = None

        logger.info("VoiceTypingEngine started")

    async def stop(self):
        """Shutdown all components."""
        if self._is_recording:
            await self.stop_recording()
        await self.hotkey_listener.stop()
        await self.window_watcher.stop()
        await self.keyboard_output.stop()
        await self.pipeline.close()
        if self._rag_ext:
            await self._rag_ext.on_stop()
        logger.info("VoiceTypingEngine stopped")

    async def start_recording(self):
        """Start voice recording: mic -> ASR -> [RAG] -> LLM -> keyboard."""
        # Debounce: prevent rapid toggling
        now = time.time()
        if now - self._last_toggle_time < self._toggle_cooldown:
            logger.debug("Recording toggle ignored (cooldown: %.1fs remaining)", 
                        self._toggle_cooldown - (now - self._last_toggle_time))
            return
        
        async with self._recording_lock:
            if self._is_recording:
                return
            if not self._asr_api_key:
                logger.error("ASR_API_KEY not set, cannot start recording")
                return

            self._last_toggle_time = now
            self._is_recording = True
            self.pipeline.clear_context()
            await self._broadcast({"type": "recording", "active": True})

            try:
                asr_config = ASRConfig(
                    name="voice_typing_asr",
                    api_key=self._asr_api_key,
                    model=self._asr_model,
                    max_silence_ms=self._asr_max_silence_ms,
                    sample_rate=16000,
                )
                
                # Select ASR extension based on provider
                if self._asr_provider == "tencent":
                    # Tencent Cloud ASR
                    if not self._asr_secret_key:
                        logger.error("Tencent ASR requires ASR_SECRET_KEY")
                        self._is_recording = False
                        return
                    
                    asr_config.custom_config["secret_key"] = self._asr_secret_key
                    self._asr_ext = TencentASRExtension(asr_config)
                    logger.info("Using TencentASRExtension for model: %s", self._asr_model)
                    
                elif self._asr_model in _QWEN_ASR_MODELS:
                    # Aliyun Qwen3-ASR
                    self._asr_ext = QwenASRExtension(asr_config)
                    logger.info("Using QwenASRExtension for model: %s", self._asr_model)
                    
                elif self._asr_model in _TENCENT_ASR_MODELS:
                    # Tencent by model name
                    if not self._asr_secret_key:
                        logger.error("Tencent ASR requires ASR_SECRET_KEY")
                        self._is_recording = False
                        return
                    
                    asr_config.custom_config["secret_key"] = self._asr_secret_key
                    self._asr_ext = TencentASRExtension(asr_config)
                    logger.info("Using TencentASRExtension for model: %s", self._asr_model)
                    
                else:
                    # Default to Aliyun Qwen3-ASR
                    self._asr_ext = QwenASRExtension(asr_config)
                    logger.info("Using QwenASRExtension (default) for model: %s", self._asr_model)

                self._asr_ext.connect("text", self._on_asr_sentence_wrapper)
                self._asr_ext.connect("partial_text", self._on_asr_partial_wrapper)
                self._asr_ext.connect("error", self._on_asr_error_wrapper)

                await self._asr_ext.on_start()

                self._microphone.on_audio(self._on_mic_audio)
                self._microphone.start(asyncio.get_event_loop())

                logger.info("Recording started (mic -> ASR -> pipeline)")
            except Exception as e:
                logger.error("Failed to start recording: %s", e)
                self._is_recording = False
                await self._broadcast({"type": "recording", "active": False})
                await self._cleanup_recording()

    async def stop_recording(self):
        """Stop voice recording and close ASR session."""
        # Debounce: prevent rapid toggling
        now = time.time()
        if now - self._last_toggle_time < self._toggle_cooldown:
            logger.debug("Recording toggle ignored (cooldown: %.1fs remaining)", 
                        self._toggle_cooldown - (now - self._last_toggle_time))
            return
        
        async with self._recording_lock:
            if not self._is_recording:
                return
            
            self._last_toggle_time = now
            self._is_recording = False
            logger.info("Recording stopping...")

            # 立即通知 UI（快速响应）
            await self._broadcast({"type": "recording", "active": False})
            
            # 后台清理资源（不阻塞 UI）
            asyncio.create_task(self._cleanup_recording())
            
            logger.info("Recording stopped")

    async def _cleanup_recording(self):
        self._microphone.stop()
        if self._asr_ext:
            try:
                await self._asr_ext.on_stop()
            except Exception as e:
                logger.warning("ASR stop error: %s", e)
            self._asr_ext = None

    async def _on_mic_audio(self, pcm_data: bytes):
        if self._asr_ext and self._asr_ext.lifecycle.is_ready():
            await self._asr_ext.on_data("audio_frame", pcm_data)

    async def _on_asr_error_wrapper(self, error_msg: str):
        logger.error("ASR connection lost: %s, stopping recording", error_msg)
        await self._broadcast({"type": "asr_error", "message": str(error_msg)})
        task = asyncio.create_task(self.stop_recording(), name="asr-error-stop")
        task.add_done_callback(_task_done_callback)

    async def _on_asr_partial_wrapper(self, text: str):
        await self._broadcast({"type": "asr_partial", "text": text})

    async def _on_asr_sentence_wrapper(self, text: str):
        logger.info("ASR sentence: '%s'", text)
        await self._broadcast({"type": "asr_final", "text": text})
        task = asyncio.create_task(self._process_sentence(text), name="process-sentence")
        task.add_done_callback(_task_done_callback)

    async def _process_sentence(self, text: str):
        try:
            rag_context = None
            if self._rag_ext:
                try:
                    rag_context = await asyncio.wait_for(
                        self._rag_ext._retrieve(text),
                        timeout=RAG_TIMEOUT_S,
                    )
                    if rag_context:
                        logger.info("RAG hit for ASR text, injecting context")
                except asyncio.TimeoutError:
                    logger.debug("RAG retrieval timed out, proceeding without")
                except Exception as e:
                    logger.warning("RAG retrieval error: %s", e)

            self.pipeline.set_rag_context(rag_context)
            await self.pipeline.process_asr_text(text)
        except Exception as e:
            logger.error("Sentence processing failed: %s", e)

    async def _on_window_change(self, window: WindowInfo):
        if self._scene_override:
            return
        scene = self.scene_classifier.classify(window)
        self.pipeline.set_scene(scene)
        logger.info("Auto scene: %s (window: %s)", scene.name, window.app_name)
        await self._broadcast({
            "type": "scene_change",
            "scene": scene.name,
            "display_name": scene.display_name,
        })

    async def _on_raw_text(self, text: str):
        await self._broadcast({"type": "raw_text", "text": text})

    async def _on_final_text_stream(self, chunk: str):
        await self._broadcast({"type": "final_text", "text": chunk})

    async def _on_final_complete(self, text: str):
        await self.keyboard_output.type_text(text)
        await self._broadcast({"type": "final_complete", "text": text})

    def add_ws_client(self, ws: WebSocket):
        self._ws_clients.append(ws)

    def remove_ws_client(self, ws: WebSocket):
        if ws in self._ws_clients:
            self._ws_clients.remove(ws)

    async def _broadcast(self, data: dict):
        if not self._ws_clients:
            return
        message = json.dumps(data, ensure_ascii=False)
        disconnected = []
        for ws in self._ws_clients:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self._ws_clients.remove(ws)
