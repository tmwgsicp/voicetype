#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Sherpa-ONNX real-time streaming ASR extension.
基于 Sherpa-ONNX 的实时流式语音识别扩展。

Features:
- Local offline ASR (no API key required)
- Real-time streaming recognition
- Built-in VAD support
- Multi-language support
"""

import asyncio
import logging
import numpy as np
from typing import Optional, Any

try:
    import sherpa_onnx
except ImportError:
    sherpa_onnx = None

from voicetype.voiceforge.core.extension import Extension, ExtensionMeta, Port, PortType
from voicetype.voiceforge.core.config import ASRConfig
from voicetype.utils.path_helper import resolve_model_path

logger = logging.getLogger(__name__)


class SherpaASRExtension(Extension):
    """
    Sherpa-ONNX streaming ASR extension.
    使用本地 ONNX 模型的实时流式语音识别。
    """
    
    # 定义输入输出端口
    metadata = ExtensionMeta(
        name="sherpa_asr",
        description="Sherpa-ONNX local offline ASR",
        category="asr",
    )
    input_ports = [
        Port("audio_frame", PortType.AUDIO_FRAME, "PCM 16kHz audio frame"),
    ]
    output_ports = [
        Port("text", PortType.TEXT, "Final recognition text"),
        Port("partial_text", PortType.TEXT, "Intermediate recognition result", required=False),
    ]

    def __init__(self, config: ASRConfig):
        if sherpa_onnx is None:
            raise ImportError("sherpa-onnx not installed. Install: pip install sherpa-onnx")
        
        super().__init__(config)
        
        # 从配置中获取模型路径
        model_dir = self.config.custom_config.get("model_dir", "models/sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23")
        
        # 解析为绝对路径
        model_dir = resolve_model_path(model_dir)
        
        # 检测是否为双语模型
        is_bilingual = "bilingual" in model_dir.lower() or "zh-en" in model_dir.lower()
        
        logger.info(f"Initializing Sherpa-ONNX ASR with model: {model_dir}")
        logger.info(f"Model type: {'Bilingual (中英混合)' if is_bilingual else 'Chinese-only (纯中文)'}")
        
        # 使用新版 API 初始化识别器
        try:
            self._recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
                tokens=f"{model_dir}/tokens.txt",
                encoder=f"{model_dir}/encoder-epoch-99-avg-1.onnx",
                decoder=f"{model_dir}/decoder-epoch-99-avg-1.onnx",
                joiner=f"{model_dir}/joiner-epoch-99-avg-1.onnx",
                num_threads=4,
                sample_rate=16000,
                feature_dim=80,
                enable_endpoint_detection=True,
                rule1_min_trailing_silence=2.0,  # 提高到2s，减少误触发
                rule2_min_trailing_silence=1.4,  # 提高到1.4s
                rule3_min_utterance_length=25.0,  # 提高到25，避免过短片段
                decoding_method="greedy_search",
                max_active_paths=4,
                hotwords_score=1.5,
                provider="cpu",
            )
        except Exception as e:
            logger.error(f"Failed to initialize Sherpa-ONNX recognizer: {e}")
            raise
        
        self._stream: Optional[sherpa_onnx.OnlineStream] = None
        self._last_text = ""
        
        logger.info(f"[{self.config.name}] Sherpa-ONNX ASR initialized successfully")

    async def _do_start(self):
        """启动识别器"""
        self._stream = self._recognizer.create_stream()
        self._last_text = ""
        logger.info(f"[{self.config.name}] Sherpa-ONNX stream created")

    async def _do_stop(self):
        """停止识别器"""
        self._stream = None
        self._last_text = ""
        logger.info(f"[{self.config.name}] Sherpa-ONNX stream closed")

    async def send_audio(self, audio_data: bytes):
        """
        Send audio data for recognition.
        发送音频数据进行识别。
        
        Args:
            audio_data: PCM 16-bit audio bytes (16kHz, mono)
        """
        if not self._stream:
            logger.warning(f"[{self.config.name}] Stream not ready, ignoring audio")
            return
        
        try:
            # 转换为 float32 samples
            samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # 发送给识别器
            self._stream.accept_waveform(16000, samples)
            
            # 检查是否有识别结果
            while self._recognizer.is_ready(self._stream):
                self._recognizer.decode_stream(self._stream)
            
            # 获取部分结果（新版API直接返回字符串）
            partial_text = self._recognizer.get_result(self._stream)
            
            # 发送部分结果（不记录日志，减少输出）
            if partial_text and partial_text != self._last_text:
                self._last_text = partial_text
                await self.send("partial_text", partial_text)
            
            # 检查是否到达端点（句子结束）
            is_endpoint = self._recognizer.is_endpoint(self._stream)
            if is_endpoint:
                # 获取最终结果
                final_text = self._recognizer.get_result(self._stream)
                
                # 只记录非空的最终结果（与商用版保持一致）
                if final_text.strip():
                    logger.info(f"ASR recognized: '{final_text}'")
                    await self.send("text", final_text)
                
                # 重置流，准备下一句
                self._recognizer.reset(self._stream)
                self._last_text = ""
        except Exception as e:
            logger.error(f"[{self.config.name}] Error in send_audio: {e}", exc_info=True)
            raise

    async def _do_cleanup(self):
        """清理资源"""
        self._stream = None
        self._recognizer = None
        logger.info(f"[{self.config.name}] Sherpa-ONNX cleanup complete")

    async def on_data(self, port: str, data: Any):
        """
        接收输入数据（实现基类抽象方法）
        
        Args:
            port: 输入端口名称
            data: 音频数据 (bytes)
        """
        if port == "audio_frame":
            await self.send_audio(data)
