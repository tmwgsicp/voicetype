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
from .voiceforge.extensions.providers.sherpa.asr_sherpa import SherpaASRExtension
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
        asr_vad_threshold: float = 0.5,
        voiceprint_threshold: float = 0.5,
        sherpa_model_dir: str = "models/sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23",
        sherpa_kws_enabled: bool = False,
        sherpa_kws_model_dir: str = "models/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01",
        sherpa_keywords: list[str] = None,
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
            asr_provider: ASR provider (aliyun/tencent/sherpa, from config)
            asr_api_key: ASR API key (from config)
            asr_secret_key: Tencent Cloud SecretKey (from config)
            asr_model: ASR model name (from config)
            asr_max_silence_ms: VAD silence threshold (from config)
            asr_vad_threshold: VAD sensitivity (0.0-1.0, from config)
            voiceprint_threshold: Voiceprint verification threshold (from config)
            sherpa_model_dir: Sherpa-ONNX ASR model directory (from config)
            sherpa_kws_enabled: Enable keyword spotting (from config)
            sherpa_kws_model_dir: Sherpa-ONNX KWS model directory (from config)
            sherpa_keywords: Custom wake words list (from config)
            hotkey: Global hotkey (from config)
            typing_delay_ms: Typing delay (from config)
        """
        self._asr_provider = asr_provider
        self._asr_api_key = asr_api_key
        self._asr_secret_key = asr_secret_key
        self._asr_model = asr_model
        self._asr_max_silence_ms = asr_max_silence_ms
        self._asr_vad_threshold = asr_vad_threshold
        self._sherpa_model_dir = sherpa_model_dir
        self._sherpa_kws_enabled = sherpa_kws_enabled
        self._sherpa_kws_model_dir = sherpa_kws_model_dir
        self._sherpa_keywords = sherpa_keywords or ["语音输入", "开始输入"]
        self._asr_ext: Optional[BaseASRExtension] = None
        self._kws_ext: Optional[Any] = None  # KWS扩展

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
                    "threshold": voiceprint_threshold
                }
            )
            logger.info("Voiceprint service (LOCAL_ONNX) initialized")
        except Exception as e:
            logger.warning(f"Voiceprint service initialization failed: {e}")
            self._voiceprint_service = None

        self._voiceprint_enabled = False
        
        # KWS initialization (if enabled)
        if self._sherpa_kws_enabled:
            self._init_kws()
        
        # Audio buffer for voiceprint verification
        self._audio_buffer: list[bytes] = []
        self._voiceprint_check_buffer: list[bytes] = []  # 声纹验证音频缓冲（VAD触发式）
        self._is_speaking = False  # 当前是否在说话（VAD状态）
        self._current_speech_verified = False  # 当前这段话是否已验证通过
        self._voiceprint_check_done = False  # 声纹是否已检查过（无论通过或拒绝）
        self._voiceprint_checking_in_progress = False  # 是否正在验证中（防止重复验证）
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
    
    async def _on_kws_audio_wrapper(self, pcm_data: bytes):
        """KWS音频回调包装器"""
        await self._on_mic_audio(pcm_data)
    
    def _init_kws(self):
        """初始化关键词唤醒（KWS）"""
        try:
            from .voiceforge.extensions.providers.sherpa.kws_sherpa import SherpaKWSExtension
            from .voiceforge.core.config import ExtensionConfig
            
            # 写入关键词文件
            import os
            keywords_file = os.path.join(self._sherpa_kws_model_dir, "keywords.txt")
            os.makedirs(self._sherpa_kws_model_dir, exist_ok=True)
            with open(keywords_file, "w", encoding="utf-8") as f:
                for kw in self._sherpa_keywords:
                    f.write(f"{kw}\n")
            
            logger.info(f"KWS keywords written to {keywords_file}: {self._sherpa_keywords}")
            
            # 定义关键词检测回调
            async def on_keyword_detected(keyword: str):
                logger.info(f"Wake word '{keyword}' detected, auto-starting recording...")
                await self._broadcast({"type": "keyword_detected", "keyword": keyword})
                # 自动开始录音
                if not self._is_recording:
                    await self.start_recording()
            
            # 初始化KWS扩展
            kws_config = ExtensionConfig(
                name="sherpa_kws",
                category="kws",
                custom_config={
                    "model_dir": self._sherpa_kws_model_dir,
                    "keywords_file": keywords_file,
                    "keywords": self._sherpa_keywords,  # 传递用户定义的关键词
                }
            )
            self._kws_ext = SherpaKWSExtension(kws_config, on_keyword_callback=on_keyword_detected)
            logger.info(f"KWS initialized with keywords: {self._sherpa_keywords}")
        except Exception as e:
            logger.error(f"Failed to initialize KWS: {e}", exc_info=True)
            self._kws_ext = None

    async def start(self):
        """Initialize all components."""
        await self.keyboard_output.start()
        await self.window_watcher.start()
        await self.hotkey_listener.start()
        
        # 启动KWS（如果启用）
        if self._kws_ext:
            try:
                await self._kws_ext.on_start()  # 使用 on_start()
                # 启动麦克风用于KWS监听
                self._microphone.on_audio(self._on_kws_audio_wrapper)  # 使用 on_audio()
                loop = asyncio.get_event_loop()
                self._microphone.start(loop)  # 传递 event loop
                logger.info("KWS started, listening for wake words...")
            except Exception as e:
                logger.error(f"Failed to start KWS: {e}")
        
        logger.info("VoiceTypingEngine started")

    async def stop(self):
        """Shutdown all components."""
        if self._is_recording:
            await self.stop_recording()
        await self.hotkey_listener.stop()
        await self.window_watcher.stop()
        await self.keyboard_output.stop()
        await self.pipeline.close()
        
        # 停止KWS
        if self._kws_ext:
            try:
                await self._kws_ext.on_stop()
                logger.info("KWS stopped")
            except Exception as e:
                logger.error(f"Failed to stop KWS: {e}")
        
        logger.info("VoiceTypingEngine stopped")
    
    async def reload_kws_keywords(self, new_keywords: list[str]):
        """
        热更新KWS关键词，无需重启后端。
        Hot reload KWS keywords without backend restart.

        Args:
            new_keywords: 新的关键词列表 (e.g., ['小明同学', '你好语音'])
        """
        if not self._sherpa_kws_enabled or not self._kws_ext:
            logger.warning("KWS is not enabled, cannot reload keywords")
            return False

        try:
            logger.info(f"Reloading KWS keywords: {new_keywords}")

            # 1. 停止当前KWS
            await self._kws_ext.on_stop()

            # 2. 更新关键词
            self._sherpa_keywords = new_keywords

            # 3. 重新初始化KWS
            self._init_kws()

            # 4. 重新启动KWS
            if self._kws_ext:
                await self._kws_ext.on_start()
                logger.info(f"KWS keywords reloaded successfully: {new_keywords}")
                return True
            else:
                logger.error("Failed to reinitialize KWS after keyword reload")
                return False

        except Exception as e:
            logger.error(f"Failed to reload KWS keywords: {e}", exc_info=True)
            return False
    
    async def enable_kws(self, sherpa_kws_model_dir: str, sherpa_keywords: list[str]):
        """
        启用 KWS 语音唤醒功能。
        Enable KWS wake word detection.
        
        Args:
            sherpa_kws_model_dir: KWS 模型目录
            sherpa_keywords: 唤醒词列表
        """
        try:
            logger.info(f"Enabling KWS with keywords: {sherpa_keywords}")
            
            # 更新配置
            self._sherpa_kws_enabled = True
            self._sherpa_kws_model_dir = sherpa_kws_model_dir
            self._sherpa_keywords = sherpa_keywords
            
            # 初始化 KWS
            self._init_kws()
            
            # 启动 KWS
            if self._kws_ext:
                await self._kws_ext.on_start()
                # 如果不在录音状态，启动麦克风用于 KWS 监听
                if not self._is_recording:
                    self._microphone.on_audio(self._on_kws_audio_wrapper)
                    loop = asyncio.get_event_loop()
                    self._microphone.start(loop)
                logger.info("✓ KWS enabled successfully")
                return True
            else:
                logger.error("Failed to initialize KWS")
                return False
        
        except Exception as e:
            logger.error(f"Failed to enable KWS: {e}", exc_info=True)
            return False
    
    async def disable_kws(self):
        """
        禁用 KWS 语音唤醒功能。
        Disable KWS wake word detection.
        """
        try:
            logger.info("Disabling KWS")
            
            # 更新配置
            self._sherpa_kws_enabled = False
            
            # 停止 KWS
            if self._kws_ext:
                await self._kws_ext.on_stop()
                logger.info("✓ KWS stopped")
            
            # 停止麦克风（如果不在录音状态）
            if not self._is_recording:
                self._microphone.stop()
                logger.info("✓ Microphone stopped (KWS disabled)")
            
            self._kws_ext = None
            logger.info("✓ KWS disabled successfully")
            return True
        
        except Exception as e:
            logger.error(f"Failed to disable KWS: {e}", exc_info=True)
            return False

    def reload_llm_config(self, llm_api_key: str, llm_base_url: str, llm_model: str):
        """
        热更新 LLM 配置，无需重启后端。
        Hot reload LLM configuration without backend restart.
        
        Args:
            llm_api_key: 新的 LLM API Key
            llm_base_url: 新的 LLM Base URL
            llm_model: 新的 LLM 模型名称
        """
        try:
            logger.info(f"Reloading LLM config: model={llm_model}, base_url={llm_base_url}")
            
            # 重新创建 Pipeline（包含新的 LLM 配置）
            self.pipeline = VoiceTypingPipeline(
                llm_api_key=llm_api_key,
                llm_base_url=llm_base_url,
                llm_model=llm_model,
            )
            
            # 重新绑定回调
            self.pipeline.on_raw_text(self._on_raw_text)
            self.pipeline.on_final_text_stream(self._on_final_text_stream)
            self.pipeline.on_final_text(self._on_final_complete)
            
            # 恢复当前场景
            if self._scene_override:
                scene_name = self._scene_override
                if scene_name in SCENES:
                    self.pipeline.set_scene(SCENES[scene_name])
            
            logger.info("LLM config reloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload LLM config: {e}", exc_info=True)
            return False

    def reload_asr_config(
        self,
        asr_provider: str,
        asr_api_key: str,
        asr_secret_key: str,
        asr_model: str,
        asr_max_silence_ms: int,
        asr_vad_threshold: float,
        sherpa_model_dir: str
    ):
        """
        热更新 ASR 配置，无需重启后端。
        Hot reload ASR configuration without backend restart.
        
        Note: 如果正在录音，需要先停止录音，配置更新后重新开始。
        """
        try:
            logger.info(f"Reloading ASR config: provider={asr_provider}, model={asr_model}")
            
            # 更新配置
            self._asr_provider = asr_provider
            self._asr_api_key = asr_api_key
            self._asr_secret_key = asr_secret_key
            self._asr_model = asr_model
            self._asr_max_silence_ms = asr_max_silence_ms
            self._asr_vad_threshold = asr_vad_threshold
            self._sherpa_model_dir = sherpa_model_dir
            
            logger.info("ASR config updated. Will take effect on next recording.")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload ASR config: {e}", exc_info=True)
            return False

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
            
            # ✅ 修复: Sherpa 本地 ASR 不需要 API Key!
            if self._asr_provider != "sherpa" and not self._asr_api_key:
                logger.error(f"{self._asr_provider.upper()} ASR requires API key, cannot start recording")
                await self._broadcast({
                    "type": "error",
                    "message": f"{self._asr_provider.upper()} ASR 需要配置 API Key"
                })
                return

            self._last_toggle_time = now
            self._is_recording = True
            self.pipeline.clear_context()
            self._audio_buffer.clear()  # Clear audio buffer
            self._voiceprint_check_buffer.clear()  # 清空声纹检查缓冲
            self._current_speech_verified = False  # 重置声纹验证状态
            self._voiceprint_check_done = False  # 重置检查完成标志
            self._voiceprint_checking_in_progress = False  # 重置验证进行中标志
            self._is_speaking = False  # 重置说话状态
            self._current_speech_verified = False  # 重置验证状态
            self._speech_frame_count = 0  # 重置语音帧计数
            self._silence_frame_count = 0  # 重置静音帧计数
            
            logger.info(f"开始录音 (ASR Provider: {self._asr_provider})")
            await self._broadcast({"type": "recording", "active": True})

            try:
                # ✅ 添加详细日志
                logger.info(f"初始化 ASR: provider={self._asr_provider}, model={self._asr_model}")
                
                asr_config = ASRConfig(
                    name="voice_typing_asr",
                    api_key=self._asr_api_key or "",  # ✅ 避免 None
                    model=self._asr_model,
                    max_silence_ms=self._asr_max_silence_ms,
                    vad_threshold=self._asr_vad_threshold,
                    sample_rate=16000,
                )
                
                logger.info(f"ASR config: silence={self._asr_max_silence_ms}ms, vad_threshold={self._asr_vad_threshold}")
                
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
                    
                elif self._asr_provider == "sherpa":
                    # Sherpa-ONNX local ASR (no API key required)
                    asr_config.custom_config["model_dir"] = self._sherpa_model_dir
                    self._asr_ext = SherpaASRExtension(asr_config)
                    logger.info("Using SherpaASRExtension (local offline ASR): %s", self._sherpa_model_dir)
                    
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

                logger.info("✅ 录音启动成功! (mic -> ASR -> pipeline)")
                logger.info(f"   ASR Provider: {self._asr_provider}")
                logger.info(f"   ASR Model: {self._asr_model}")
                logger.info(f"   麦克风采样率: {self._microphone._sample_rate}Hz")
                
            except TimeoutError as e:
                logger.error(f"❌ ASR 连接超时: {e}")
                logger.error("   可能原因: 1) 网络问题 2) API Key 无效 3) 模型不可用")
                self._is_recording = False
                await self._broadcast({
                    "type": "error",
                    "message": "ASR 连接超时,请检查网络和 API Key"
                })
                await self._cleanup_recording()
            except FileNotFoundError as e:
                logger.error(f"❌ 模型文件未找到: {e}")
                logger.error("   请运行: python scripts/download_models.py")
                self._is_recording = False
                await self._broadcast({
                    "type": "error",
                    "message": "AI 模型文件缺失,请下载模型"
                })
                await self._cleanup_recording()
            except Exception as e:
                logger.error(f"❌ 录音启动失败: {e}", exc_info=True)
                self._is_recording = False
                await self._broadcast({
                    "type": "error",
                    "message": f"录音启动失败: {str(e)}"
                })
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
        
        # 4. 如果KWS启用，重新启动麦克风用于KWS监听
        if self._kws_ext and self._sherpa_kws_enabled:
            try:
                loop = asyncio.get_event_loop()
                self._microphone.start(loop)
                logger.info("  ✓ Microphone restarted for KWS")
            except Exception as e:
                logger.warning("  ✗ Failed to restart microphone for KWS: %s", e)
        
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
        
        策略：
        0. KWS（如果启用）：持续监听唤醒词，检测到后自动开始录音
        1. 本地 ASR (Sherpa): 本地 VAD + 声纹验证后再发送
        2. 云端 ASR (阿里云/腾讯云): 累积音频用于声纹验证，同时转发到云端
        """
        # === KWS唤醒词检测（持续监听） ===
        if self._kws_ext and self._sherpa_kws_enabled and not self._is_recording:
            try:
                await self._kws_ext.send_audio(pcm_data)
            except Exception as e:
                logger.error(f"KWS error: {e}")
        
        # 如果不在录音状态，只做KWS检测
        if not self._is_recording:
            return
        
        if not self._asr_ext:
            return
        
        if not self._asr_ext.lifecycle.is_ready():
            return
        
        # === 云端 ASR：音频转发 + 声纹后验证 ===
        if self._asr_provider in ["aliyun", "tencent"]:
            # ✅ 云端ASR：始终发送音频（无法预先判断说话段落）
            # 声纹验证在ASR输出时进行，更灵活准确
            await self._asr_ext.send_audio(pcm_data)
            
            # 如果启用声纹，累积音频用于后续验证
            if self._voiceprint_enabled and self._voiceprint_service:
                # 持续累积音频，保留最近2秒用于验证
                self._voiceprint_check_buffer.append(pcm_data)
                total_check_bytes = sum(len(chunk) for chunk in self._voiceprint_check_buffer)
                
                # 保留最近2秒音频（32000字节 = 16000Hz * 2bytes * 2s）
                # 当ASR输出句子时，用这2秒音频验证
                max_buffer_bytes = 16000 * 2 * 2.0
                if total_check_bytes > max_buffer_bytes:
                    # 删除最旧的音频块
                    while total_check_bytes > max_buffer_bytes and self._voiceprint_check_buffer:
                        removed = self._voiceprint_check_buffer.pop(0)
                        total_check_bytes -= len(removed)
            
            return
        
        # === 本地 ASR (Sherpa)：声纹前验证（如果启用） ===
        # 前验证策略：
        # 1. 累积音频直到足够（1秒）
        # 2. 进行声纹验证
        # 3. 验证通过 → 批量发送缓冲区音频 + 继续正常录音
        # 4. 验证失败 → 清空缓冲区并停止录音
        # 5. 验证未完成（<1秒）→ 不发送音频到 ASR（等待验证结果）
        
        if self._voiceprint_enabled and self._voiceprint_service:
            # 累积音频到验证缓冲区
            self._voiceprint_check_buffer.append(pcm_data)
            total_check_bytes = sum(len(chunk) for chunk in self._voiceprint_check_buffer)
            
            # 当累积足够音频（1秒）且尚未验证时，进行声纹验证
            if not self._voiceprint_check_done and total_check_bytes >= 16000 * 2 * 1.0:
                self._voiceprint_checking_in_progress = True
                logger.info(f"✓ Accumulated {total_check_bytes / (16000 * 2):.1f}s audio, starting voiceprint verification")
                try:
                    audio_bytes = b"".join(self._voiceprint_check_buffer)
                    
                    # 查找已注册的声纹
                    voiceprints_dir = get_config_dir() / "voiceprints"
                    verification_passed = False
                    
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
                                    logger.info(f"✓ Voiceprint PASS (score={result.score:.2f} >= threshold={self._voiceprint_service.threshold}), sending buffered audio to ASR")
                                    verification_passed = True
                                else:
                                    logger.warning(f"✗ Voiceprint REJECT (score={result.score:.2f} < threshold={self._voiceprint_service.threshold}), stopping recording")
                                    await self._broadcast({
                                        "type": "voiceprint_reject",
                                        "score": result.score,
                                        "message": "非本人音频，已拦截",
                                    })
                                    # 清空所有缓冲区并停止录音
                                    self._audio_buffer.clear()
                                    self._voiceprint_check_buffer.clear()
                                    self._voiceprint_check_done = True
                                    await self.stop_recording()
                                    return
                        else:
                            # 没有注册声纹，默认通过
                            logger.info("No voiceprint registered, allowing by default")
                            verification_passed = True
                    else:
                        # 声纹目录不存在，默认通过
                        logger.info("Voiceprint directory not found, allowing by default")
                        verification_passed = True
                    
                    # 验证通过：批量发送缓冲区中的音频到 ASR
                    if verification_passed:
                        logger.info(f"Sending {len(self._voiceprint_check_buffer)} buffered audio chunks to ASR")
                        for chunk in self._voiceprint_check_buffer:
                            try:
                                await self._asr_ext.on_data("audio_frame", chunk)
                            except Exception as e:
                                logger.error(f"Failed to send buffered audio to ASR: {e}")
                        
                        self._voiceprint_check_buffer.clear()
                        self._voiceprint_check_done = True
                        self._current_speech_verified = True
                        
                except Exception as e:
                    logger.error(f"Voiceprint verification error: {e}, allowing by default")
                    # 错误时默认通过，发送缓冲区音频
                    for chunk in self._voiceprint_check_buffer:
                        try:
                            await self._asr_ext.on_data("audio_frame", chunk)
                        except Exception as e:
                            logger.error(f"Failed to send buffered audio to ASR: {e}")
                    self._voiceprint_check_buffer.clear()
                    self._voiceprint_check_done = True
                    self._current_speech_verified = True
                finally:
                    self._voiceprint_checking_in_progress = False
            
            # 验证未完成（<1秒）→ 不发送到 ASR，继续累积
            if not self._voiceprint_check_done:
                return
            
            # 验证已完成且失败 → 不应该到这里（已在上面 return）
            if not self._current_speech_verified:
                logger.debug("Voiceprint rejected, dropping audio frame")
                return
        
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

        对于云端ASR：在句子输出时验证声纹（后验证）
        对于本地ASR：声纹已在音频发送前验证（前验证）
        """
        logger.info("ASR sentence: '%s'", text)
        await self._broadcast({"type": "asr_final", "text": text})

        # === 云端ASR的声纹后验证：用缓冲区中的音频验证 ===
        if self._voiceprint_enabled and self._voiceprint_service and self._asr_provider in ["aliyun", "tencent"]:
            # 使用缓冲区中的音频进行声纹验证
            if self._voiceprint_check_buffer:
                audio_bytes = b"".join(self._voiceprint_check_buffer)
                
                try:
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
                                
                                if not result.decision:
                                    logger.info(f"Voiceprint blocked ASR output: '{text}' (score={result.score:.2f} < threshold={self._voiceprint_service.threshold})")
                                    await self._broadcast({
                                        "type": "voiceprint_reject",
                                        "score": result.score,
                                        "message": "非本人音频，已拦截",
                                    })
                                    # 清理缓冲区，准备下一句
                                    self._audio_buffer.clear()
                                    self._voiceprint_check_buffer.clear()
                                    return  # 拒绝处理这段文本
                                else:
                                    logger.info(f"Voiceprint PASS for ASR output (score={result.score:.2f}, threshold={self._voiceprint_service.threshold})")
                except Exception as e:
                    logger.error(f"声纹验证出错: {e}，允许输出")
            
            # 清理缓冲区，准备下一句
            self._voiceprint_check_buffer.clear()
        
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
