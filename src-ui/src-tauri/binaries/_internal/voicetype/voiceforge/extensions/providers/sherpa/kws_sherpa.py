#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Sherpa-ONNX Keyword Spotting (KWS) extension.
基于 Sherpa-ONNX 的关键词唤醒扩展。

Features:
- Local offline keyword spotting
- Ultra-low latency (<100ms)
- Customizable keywords
- Low CPU usage
"""

import asyncio
import logging
import numpy as np
from typing import Optional, Any, List

try:
    import sherpa_onnx
except ImportError:
    sherpa_onnx = None

from voicetype.voiceforge.core.extension import Extension, ExtensionMeta, Port, PortType
from voicetype.voiceforge.core.config import ExtensionConfig
from voicetype.utils.path_helper import resolve_model_path

logger = logging.getLogger(__name__)


class SherpaKWSExtension(Extension):
    """
    Sherpa-ONNX Keyword Spotting extension.
    使用本地 ONNX 模型的关键词唤醒。
    """
    
    metadata = ExtensionMeta(
        name="sherpa_kws",
        description="Sherpa-ONNX local keyword spotting",
        category="kws",
    )
    input_ports = [
        Port("audio_frame", PortType.AUDIO_FRAME, "PCM 16kHz audio frame"),
    ]
    output_ports = [
        Port("keyword_detected", PortType.TEXT, "Detected keyword"),
    ]

    def __init__(self, config: ExtensionConfig, on_keyword_callback=None):
        if sherpa_onnx is None:
            raise ImportError("sherpa-onnx not installed. Install: pip install sherpa-onnx")
        
        super().__init__(config)
        
        # 关键词检测回调
        self._on_keyword = on_keyword_callback
        
        # 从配置中获取模型路径和关键词
        model_dir = self.config.custom_config.get(
            "model_dir", 
            "models/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01"
        )
        
        # 解析为绝对路径
        model_dir = resolve_model_path(model_dir)
        
        keywords_file = self.config.custom_config.get(
            "keywords_file",
            f"{model_dir}/keywords.txt"
        )
        
        logger.info(f"Initializing Sherpa-ONNX KWS with model: {model_dir}")
        logger.info(f"Keywords file: {keywords_file}")
        
        # 读取关键词列表并转换为拼音token
        try:
            # 如果keywords_file已存在且格式正确，直接使用
            if not keywords_file.endswith("keywords.txt"):
                keywords_file = f"{model_dir}/keywords.txt"
            
            # 生成编码后的关键词文件
            import tempfile
            import subprocess
            
            # 从配置读取用户定义的关键词
            user_keywords = self.config.custom_config.get("keywords", ["小明同学", "你好语音"])
            
            # 创建临时输入文件
            temp_input = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.txt')
            for kw in user_keywords:
                temp_input.write(f"{kw}\n")
            temp_input.close()
            
            # 使用 sherpa-onnx-cli 转换
            tokens_file = f"{model_dir}/tokens.txt"
            result = subprocess.run(
                [
                    "sherpa-onnx-cli", "text2token",
                    "--tokens", tokens_file,
                    "--tokens-type", "ppinyin",
                    temp_input.name,
                    keywords_file
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            # 读取转换后的关键词
            with open(keywords_file, "r", encoding="utf-8") as f:
                self._keywords = [line.strip() for line in f if line.strip()]
            
            logger.info(f"Converted {len(user_keywords)} keywords to tokens: {user_keywords} -> {self._keywords}")
            
            # 清理临时文件
            import os
            os.unlink(temp_input.name)
            
        except Exception as e:
            logger.error(f"Failed to convert keywords: {e}")
            self._keywords = []
            raise
        
        # 初始化KWS识别器
        try:
            self._kws = sherpa_onnx.KeywordSpotter(
                tokens=f"{model_dir}/tokens.txt",
                encoder=f"{model_dir}/encoder-epoch-12-avg-2-chunk-16-left-64.onnx",
                decoder=f"{model_dir}/decoder-epoch-12-avg-2-chunk-16-left-64.onnx",
                joiner=f"{model_dir}/joiner-epoch-12-avg-2-chunk-16-left-64.onnx",
                keywords_file=keywords_file,
                num_threads=2,
                max_active_paths=4,
                num_trailing_blanks=1,
                keywords_score=1.0,
                keywords_threshold=0.25,
                provider="cpu",
            )
        except Exception as e:
            logger.error(f"Failed to initialize Sherpa-ONNX KWS: {e}")
            raise
        
        self._stream: Optional[Any] = None
        self._enabled = True
        
        logger.info(f"[{self.config.name}] Sherpa-ONNX KWS initialized successfully")

    async def _do_start(self):
        """启动KWS"""
        self._stream = self._kws.create_stream()
        self._enabled = True
        logger.info(f"[{self.config.name}] KWS stream created, listening for keywords...")

    async def _do_stop(self):
        """停止KWS"""
        self._stream = None
        self._enabled = False
        logger.info(f"[{self.config.name}] KWS stream closed")

    async def send_audio(self, audio_data: bytes):
        """
        Send audio data for keyword detection.
        发送音频数据进行关键词检测。
        
        Args:
            audio_data: PCM 16-bit audio bytes (16kHz, mono)
        """
        if not self._stream or not self._enabled:
            return
        
        try:
            # 转换为 float32 samples
            samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # 发送给KWS
            self._stream.accept_waveform(16000, samples)
            
            # 检查是否检测到关键词
            while self._kws.is_ready(self._stream):
                self._kws.decode_stream(self._stream)
            
            # 获取检测结果 (kws.get_result返回字符串)
            result = self._kws.get_result(self._stream)
            
            # 检查是否检测到关键词 (result直接是关键词字符串)
            if result and result.strip():
                keyword = result.strip()
                logger.info(f"Keyword detected: '{keyword}'")
                
                # 调用回调
                if self._on_keyword:
                    await self._on_keyword(keyword)
                
                await self.send("keyword_detected", keyword)
                
                # 重置流，准备下一次检测
                self._kws.reset_stream(self._stream)
                
        except Exception as e:
            logger.error(f"[{self.config.name}] Error in send_audio: {e}", exc_info=True)

    async def _do_cleanup(self):
        """清理资源"""
        self._stream = None
        self._kws = None
        logger.info(f"[{self.config.name}] KWS cleanup complete")

    async def on_data(self, port: str, data: Any):
        """
        接收输入数据（实现基类抽象方法）
        
        Args:
            port: 输入端口名称
            data: 音频数据 (bytes)
        """
        if port == "audio_frame":
            await self.send_audio(data)
    
    def enable(self):
        """启用关键词检测"""
        self._enabled = True
        logger.info(f"[{self.config.name}] KWS enabled")
    
    def disable(self):
        """禁用关键词检测"""
        self._enabled = False
        logger.info(f"[{self.config.name}] KWS disabled")
