#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
VoiceTypingEngine: the central coordinator that wires everything together.
Manages lifecycle of Microphone, ASR, WindowWatcher, SceneClassifier,
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
from .platform.voiceprint.factory import VoiceprintServiceFactory
from .platform.voiceprint.base import VoiceprintProvider

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
from .config import get_config_dir

logger = logging.getLogger(__name__)


class VoiceTypingEngine:
    """Central engine coordinating all voice typing components."""

    def __init__(
        self,
        llm_api_key: str,
        llm_base_url: str,
        llm_model: str,
        asr_provider: str = "aliyun",
        asr_api_key: str = "",
        asr_secret_key: str = "",
        asr_model: str = "qwen3-asr-flash-realtime",
        asr_max_silence_ms: int = 1200,
        hotkey: str = "<ctrl>+<shift>+v",
        typing_delay_ms: int = 5,
    ):
        """
        Initialize VoiceTypingEngine.
        
        All parameters should come from VoiceTypeConfig, no hardcoded defaults.
        
        Args:
            llm_api_key: LLM API key (required)
            llm_base_url: LLM API base URL (from config)
            llm_model: LLM model name (from config)
            asr_provider: ASR provider (aliyun/tencent, from config)
            asr_api_key: ASR API key (from config)
            asr_secret_key: Tencent Cloud SecretKey (from config)
            asr_model: ASR model name (from config)
            asr_max_silence_ms: VAD silence threshold (from config)
            hotkey: Global hotkey (from config)
            typing_delay_ms: Typing delay (from config)
        """
        self._asr_provider = asr_provider
        self._asr_api_key = asr_api_key
        self._asr_secret_key = asr_secret_key
        self._asr_model = asr_model
        self._asr_max_silence_ms = asr_max_silence_ms
        self._asr_ext: Optional[BaseASRExtension] = None

        self._microphone = Microphone()
        
        # Voiceprint service (使用本地ONNX模型)
        voiceprints_dir = get_config_dir() / "voiceprints"
        try:
            self._voiceprint_service = VoiceprintServiceFactory.create_service(
                VoiceprintProvider.LOCAL_ONNX,
                {
                    "model_path": "models/speaker_recognition.onnx",
                    "storage_dir": str(voiceprints_dir),
                    "sample_rate": 16000,
                    "threshold": 0.5
                }
            )
            logger.info("Voiceprint service (LOCAL_ONNX) initialized")
        except Exception as e:
            logger.warning(f"Voiceprint service initialization failed: {e}")
            self._voiceprint_service = None
        
        self._voiceprint_enabled = False  # 默认关闭，通过API控制
        
        # Audio buffer for voiceprint verification
        self._audio_buffer: list[bytes] = []
        self._voiceprint_check_buffer: list[bytes] = []  # 声纹验证音频缓冲（VAD触发式）
        self._is_speaking = False  # 当前是否在说话（VAD状态）
        self._current_speech_verified = False  # 当前这段话是否已验证通过
        self._speech_frame_count = 0  # 连续语音帧计数
        self._silence_frame_count = 0  # 连续静音帧计数

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
        self._last_toggle_time = 0.0
        self._toggle_cooldown = 0.3
        self._scene_override: Optional[str] = None
        self._ws_clients: list[WebSocket] = []
        self._asr_connected = False  # 新增：ASR连接状态

        self.window_watcher.on_change(self._on_window_change)
        self.pipeline.on_raw_text(self._on_raw_text)
        self.pipeline.on_final_text_stream(self._on_final_text_stream)
        self.pipeline.on_final_text(self._on_final_complete)

    @property
    def is_recording(self) -> bool:
        return self._is_recording
    
    @property
    def is_asr_connected(self) -> bool:
        """ASR是否已连接就绪"""
        return self._asr_connected
    
    def set_voiceprint_enabled(self, enabled: bool):
        """启用/禁用声纹识别"""
        self._voiceprint_enabled = enabled
        logger.info(f"Voiceprint verification {'ENABLED' if enabled else 'DISABLED'}")
        logger.info(f"   - Service status: {self._voiceprint_service is not None}")
        if self._voiceprint_service:
            logger.info(f"   - Threshold: {getattr(self._voiceprint_service, 'threshold', 'N/A')}")

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
        logger.info("VoiceTypingEngine started")

    async def stop(self):
        """Shutdown all components."""
        if self._is_recording:
            await self.stop_recording()
        await self.hotkey_listener.stop()
        await self.window_watcher.stop()
        await self.keyboard_output.stop()
        await self.pipeline.close()
        logger.info("VoiceTypingEngine stopped")

    async def start_recording(self):
        """Start voice recording: mic -> ASR -> LLM -> keyboard."""
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
            self._audio_buffer.clear()  # Clear audio buffer
            self._voiceprint_check_buffer.clear()  # 清空声纹检查缓冲
            self._is_speaking = False  # 重置说话状态
            self._current_speech_verified = False  # 重置验证状态
            self._speech_frame_count = 0  # 重置语音帧计数
            self._silence_frame_count = 0  # 重置静音帧计数
            await self._broadcast({"type": "recording", "active": True})

            try:
                asr_config = ASRConfig(
                    name="voice_typing_asr",
                    api_key=self._asr_api_key,
                    model=self._asr_model,
                    max_silence_ms=self._asr_max_silence_ms,
                    sample_rate=16000,
                )
                
                logger.info(f"ASR config: silence={self._asr_max_silence_ms}ms")
                
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
                
                # 等待ASR真正就绪（最多3秒）
                max_wait = 3.0
                wait_start = time.time()
                while not self._asr_ext.lifecycle.is_ready():
                    if time.time() - wait_start > max_wait:
                        logger.error("ASR connection timeout after %.1fs", max_wait)
                        raise TimeoutError("ASR did not become ready in time")
                    await asyncio.sleep(0.1)
                
                # 标记ASR已连接
                self._asr_connected = True
                await self._broadcast({"type": "asr_connected", "connected": True})
                logger.info("ASR connected and ready (took %.2fs)", time.time() - wait_start)

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
            self._asr_connected = False  # 标记ASR已断开
            logger.info("Recording stopping...")

            # 立即通知 UI
            await self._broadcast({"type": "recording", "active": False})
            await self._broadcast({"type": "asr_connected", "connected": False})
            
            # 后台清理资源（不阻塞 UI）
            asyncio.create_task(self._cleanup_recording())
            
            logger.info("Recording stopped")

    async def _cleanup_recording(self):
        """清理录音资源"""
        logger.info("Cleaning up recording resources...")
        
        # 1. 停止麦克风
        try:
            self._microphone.stop()
            logger.info("  ✓ Microphone stopped")
        except Exception as e:
            logger.warning("  ✗ Microphone stop error: %s", e)
        
        # 2. 停止并清理ASR扩展
        if self._asr_ext:
            try:
                logger.info("  Disconnecting ASR extension...")
                await self._asr_ext.on_stop()
                logger.info("  ✓ ASR extension stopped")
            except Exception as e:
                logger.warning("  ✗ ASR stop error: %s", e)
            finally:
                # 强制清理，即使出错
                self._asr_ext = None
                logger.info("  ✓ ASR extension cleared")
        
        # 3. 清理音频缓冲
        self._audio_buffer.clear()
        self._voiceprint_check_buffer.clear()
        self._is_speaking = False
        self._current_speech_verified = False
        self._speech_frame_count = 0
        self._silence_frame_count = 0
        
        logger.info("Cleanup complete")

    def _calculate_audio_energy(self, pcm_data: bytes) -> float:
        """计算音频能量（用于VAD）"""
        import numpy as np
        audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        return float(np.sqrt(np.mean(audio_np ** 2)))
    
    async def _on_mic_audio(self, pcm_data: bytes):
        """
        Microphone audio callback.
        麦克风音频回调。
        
        新策略：稳定VAD + 每段话验证1次
        """
        if not self._asr_ext:
            return
        
        if not self._asr_ext.lifecycle.is_ready():
            return
        
        # === 计算音频能量，稳定VAD判断 ===
        energy = self._calculate_audio_energy(pcm_data)
        is_speech_frame = energy > 0.015  # 降低阈值，更容易检测到说话
        
        # 连续3帧有语音才认为是说话开始（60ms快速响应）
        # 连续20帧静音才认为是说话结束（400ms长容错，避免被噪音打断）
        if is_speech_frame:
            self._speech_frame_count += 1
            self._silence_frame_count = 0
        else:
            self._silence_frame_count += 1
            self._speech_frame_count = 0
        
        # 判断说话状态切换
        if not self._is_speaking and self._speech_frame_count >= 3:
            # 说话开始（连续3帧，快速响应）
            self._is_speaking = True
            self._current_speech_verified = False
            self._voiceprint_check_buffer.clear()
            logger.info("Speech start detected, preparing voiceprint verification")
        elif self._is_speaking and self._silence_frame_count >= 20:
            # 说话结束（连续10帧静音）
            self._is_speaking = False
            self._voiceprint_check_buffer.clear()
            logger.info("Speech end detected, waiting for next utterance")
        
        # === 声纹验证（只在每段话开始时验证1次） ===
        if self._voiceprint_enabled and self._voiceprint_service and self._is_speaking:
            # 累积音频到验证缓冲区
            self._voiceprint_check_buffer.append(pcm_data)
            total_check_bytes = sum(len(chunk) for chunk in self._voiceprint_check_buffer)
            
            # 当累积足够音频（1秒）且当前段话尚未验证时，进行验证
            if not self._current_speech_verified and total_check_bytes >= 16000 * 2 * 1.0:
                logger.debug(f"Accumulated {total_check_bytes} bytes ({total_check_bytes / (16000 * 2):.1f}s), starting verification")
                try:
                    audio_bytes = b"".join(self._voiceprint_check_buffer)
                    
                    # 查找已注册的声纹
                    voiceprints_dir = get_config_dir() / "voiceprints"
                    if voiceprints_dir.exists():
                        vp_files = list(voiceprints_dir.glob("*.json"))
                        if vp_files:
                            import json
                            with open(vp_files[0], 'r', encoding='utf-8') as f:
                                vp_data = json.load(f)
                                speaker_id = vp_data.get("speaker_id")
                            
                            if speaker_id:
                                result = await self._voiceprint_service.verify(speaker_id, audio_bytes)
                                
                                if result.decision:
                                    logger.info(f"Voiceprint PASS (score={result.score:.1f}, threshold={self._voiceprint_service.threshold}), allowing speech")
                                    self._current_speech_verified = True
                                else:
                                    logger.warning(f"Voiceprint REJECT (score={result.score:.1f} < threshold={self._voiceprint_service.threshold}), blocking speech")
                                    self._current_speech_verified = False
                                    await self._broadcast({
                                        "type": "voiceprint_reject",
                                        "score": result.score,
                                        "message": "非本人音频",
                                    })
                                    return  # 拦截本段话
                        else:
                            # 没有注册声纹，默认通过
                            logger.info("No voiceprint registered, allowing by default")
                            self._current_speech_verified = True
                    else:
                        # 声纹目录不存在，默认通过
                        logger.info("Voiceprint directory not found, allowing by default")
                        self._current_speech_verified = True
                except Exception as e:
                    logger.error(f"声纹验证出错: {e}，降级允许通过")
                    self._current_speech_verified = True
            
            # 如果当前段话未验证通过，直接丢弃音频
            if not self._current_speech_verified:
                return  # 🛑 静默丢弃，等待下一段话
        
        # === 音频通过验证，发送到ASR ===
        # Buffer audio for final verification (keep last 5 seconds)
        self._audio_buffer.append(pcm_data)
        max_buffer_bytes = 16000 * 2 * 5
        total_bytes = sum(len(chunk) for chunk in self._audio_buffer)
        while total_bytes > max_buffer_bytes and len(self._audio_buffer) > 1:
            removed = self._audio_buffer.pop(0)
            total_bytes -= len(removed)
        
        # Send to ASR
        try:
            await self._asr_ext.on_data("audio_frame", pcm_data)
        except Exception as e:
            logger.error("Failed to send audio to ASR: %s", e)
            await self._on_asr_error_wrapper(str(e))

    async def _on_asr_error_wrapper(self, error_msg: str):
        logger.error("ASR connection lost: %s, stopping recording", error_msg)
        await self._broadcast({"type": "asr_error", "message": str(error_msg)})
        task = asyncio.create_task(self.stop_recording(), name="asr-error-stop")
        task.add_done_callback(_task_done_callback)

    async def _on_asr_partial_wrapper(self, text: str):
        await self._broadcast({"type": "asr_partial", "text": text})

    async def _on_asr_sentence_wrapper(self, text: str):
        """
        ASR final sentence callback.
        ASR 完成回调。
        
        注意：声纹验证已在麦克风回调中完成，这里直接处理。
        """
        logger.info("ASR sentence: '%s'", text)
        await self._broadcast({"type": "asr_final", "text": text})
        
        # Clear buffer for next utterance
        self._audio_buffer.clear()
        
        # Process sentence normally
        task = asyncio.create_task(self._process_sentence(text), name="process-sentence")
        task.add_done_callback(_task_done_callback)

    async def _process_sentence(self, text: str):
        try:
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
