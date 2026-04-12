#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Local ONNX-based speaker verification service.
本地 ONNX 说话人识别服务。

Uses sherpa-onnx for high-quality, lightweight speaker recognition.
使用 sherpa-onnx 实现高质量、轻量化的说话人识别。
"""

import os
import json
import logging
import numpy as np
from pathlib import Path
from typing import Optional, Dict

try:
    import sherpa_onnx
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

from .base import BaseVoiceprintService, VoiceprintResult, VoiceprintProvider

logger = logging.getLogger(__name__)


class LocalVoiceprintService(BaseVoiceprintService):
    """
    本地 ONNX 说话人识别服务。
    
    Features:
    - Zero server dependency / 零服务器依赖
    - Privacy-preserving / 隐私保护
    - Cross-platform / 跨平台
    - Lightweight (~15MB model) / 轻量化
    """
    
    def __init__(self, model_path: str, storage_dir: str, sample_rate: int = 16000, threshold: float = 0.5):
        """
        初始化本地声纹服务。
        
        Args:
            model_path: ONNX 模型路径
            storage_dir: 声纹数据存储目录
            sample_rate: 采样率 (Hz)
            threshold: 相似度阈值 (0.0-1.0)
        """
        self.model_path = Path(model_path)
        self.storage_dir = Path(storage_dir)
        self.sample_rate = sample_rate
        self.threshold = threshold
        
        # 确保存储目录存在
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化 sherpa-onnx 提取器
        try:
            config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(self.model_path),
                num_threads=2,
                debug=False,
                provider="cpu"
            )
            self.extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
            logger.info(f"LocalVoiceprintService initialized with model: {self.model_path.name}")
        except Exception as e:
            logger.error(f"Failed to initialize speaker embedding extractor: {e}")
            raise
    
    def get_provider_name(self) -> str:
        return "本地 ONNX"
    
    def is_available(self) -> bool:
        return self.model_path.exists() and self.extractor is not None
    
    def _voiceprint_file(self, speaker_id: str) -> Path:
        """获取声纹数据文件路径"""
        return self.storage_dir / f"{speaker_id}.json"
    
    def _extract_embedding(self, audio: bytes) -> np.ndarray:
        """
        提取声纹特征向量。
        
        Args:
            audio: WAV 音频数据（16kHz mono PCM）
        
        Returns:
            归一化后的特征向量
        """
        # logger.debug(f"Received audio data: {len(audio)} bytes")  # 注释掉，减少日志
        
        try:
            # 直接解析 WAV 文件（前端已经生成标准 WAV 格式）
            import wave
            import io
            
            with wave.open(io.BytesIO(audio), 'rb') as wav:
                # 验证格式
                channels = wav.getnchannels()
                rate = wav.getframerate()
                frames = wav.getnframes()
                
                # logger.debug(f"WAV format: channels={channels}, rate={rate}Hz, frames={frames}")  # 注释掉
                
                if channels != 1:
                    raise ValueError(f"Expected mono audio, got {channels} channels")
                if rate != self.sample_rate:
                    raise ValueError(f"Expected {self.sample_rate}Hz, got {rate}Hz")
                
                # 读取音频数据
                audio_data = wav.readframes(frames)
                # logger.debug(f"Read {len(audio_data)} bytes of audio data")  # 注释掉
            
            # 将 bytes 转为 float32 numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            # logger.debug(f"Converted to numpy array: shape={audio_np.shape}, dtype={audio_np.dtype}")  # 注释掉
            
        except Exception as e:
            # logger.debug(f"Audio parsing error: {e}")  # 降级为debug
            # logger.debug("Attempting fallback: direct PCM parsing")  # 降级为debug
            # 如果解析失败，尝试直接解析为 PCM
            audio_np = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
            # logger.debug(f"Fallback numpy array: shape={audio_np.shape}, dtype={audio_np.dtype}")  # 注释掉
        
        # 使用 sherpa-onnx 提取特征
        # logger.debug("Creating stream for feature extraction")  # 注释掉
        stream = self.extractor.create_stream()
        stream.accept_waveform(self.sample_rate, audio_np)
        stream.input_finished()
        
        # 提取嵌入向量
        # logger.debug("Computing embedding...")  # 注释掉
        embedding = self.extractor.compute(stream)
        # logger.debug(f"Embedding extracted: size={len(embedding)}")  # 注释掉
        
        return np.array(embedding)
    
    def _cosine_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """计算余弦相似度"""
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(emb1, emb2) / (norm1 * norm2))
    
    async def apply_digit(self, speaker_id: str) -> Optional[str]:
        """本地方案不需要数字串"""
        return None
    
    async def enroll(
        self,
        speaker_id: str,
        audio: bytes,
        digit: Optional[str] = None
    ) -> VoiceprintResult:
        """
        注册声纹（支持多轮累积）
        Multi-round enrollment with embedding averaging.
        
        Args:
            speaker_id: 说话人ID
            audio: 音频数据
            digit: 未使用（保持接口兼容）
        """
        try:
            # 提取当前音频特征
            embedding = self._extract_embedding(audio)
            
            voiceprint_file = self._voiceprint_file(speaker_id)
            
            # 检查是否已存在声纹（多轮录入）
            if voiceprint_file.exists():
                with open(voiceprint_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                
                # 获取已有的embedding列表
                existing_embeddings = existing_data.get("embeddings", [])
                
                # 添加新的embedding
                existing_embeddings.append(embedding.tolist())
                
                # 计算平均embedding
                avg_embedding = np.mean([np.array(emb) for emb in existing_embeddings], axis=0)
                
                # 存储更新后的声纹数据
                voiceprint_data = {
                    "speaker_id": speaker_id,
                    "embedding": avg_embedding.tolist(),
                    "embeddings": existing_embeddings,
                    "enrollment_rounds": len(existing_embeddings),
                    "threshold": self.threshold
                }
                
                logger.info(f"Updated voiceprint for {speaker_id} (round {len(existing_embeddings)})")
            else:
                # 首次注册
                voiceprint_data = {
                    "speaker_id": speaker_id,
                    "embedding": embedding.tolist(),
                    "embeddings": [embedding.tolist()],
                    "enrollment_rounds": 1,
                    "threshold": self.threshold
                }
                
                logger.info(f"Enrolled voiceprint for {speaker_id} (round 1)")
            
            # 保存到文件
            with open(voiceprint_file, 'w', encoding='utf-8') as f:
                json.dump(voiceprint_data, f)
            
            rounds = voiceprint_data["enrollment_rounds"]
            return VoiceprintResult(
                success=True,
                score=100.0,
                decision=True,
                message=f"注册成功 (第{rounds}轮)",
                provider=self.get_provider_name()
            )
            
        except Exception as e:
            logger.error(f"Error enrolling voiceprint: {e}")
            return VoiceprintResult(
                success=False,
                score=0.0,
                decision=False,
                message=f"注册失败: {str(e)}",
                provider=self.get_provider_name()
            )
    
    async def verify(
        self,
        speaker_id: str,
        audio: bytes,
        digit: Optional[str] = None
    ) -> VoiceprintResult:
        """验证声纹"""
        try:
            voiceprint_file = self._voiceprint_file(speaker_id)
            
            if not voiceprint_file.exists():
                return VoiceprintResult(
                    success=False,
                    score=0.0,
                    decision=False,
                    message=f"未找到声纹: {speaker_id}",
                    provider=self.get_provider_name()
                )
            
            # 加载已注册的声纹
            with open(voiceprint_file, 'r', encoding='utf-8') as f:
                voiceprint_data = json.load(f)
            
            stored_embedding = np.array(voiceprint_data["embedding"])
            threshold = voiceprint_data.get("threshold", self.threshold)
            
            # 提取当前音频特征
            current_embedding = self._extract_embedding(audio)
            
            # 计算相似度
            similarity = self._cosine_similarity(stored_embedding, current_embedding)
            decision = similarity >= threshold
            
            return VoiceprintResult(
                success=True,
                score=float(similarity),  # 保持 0-1 范围，不乘100
                decision=decision,
                message=f"相似度: {similarity:.2f} (阈值: {threshold:.2f})",
                provider=self.get_provider_name()
            )
            
        except Exception as e:
            logger.error(f"Error verifying voiceprint: {e}")
            return VoiceprintResult(
                success=False,
                score=0.0,
                decision=False,
                message=f"验证失败: {str(e)}",
                provider=self.get_provider_name()
            )
    
    async def update(
        self,
        speaker_id: str,
        audio: bytes,
        digit: Optional[str] = None
    ) -> VoiceprintResult:
        """更新声纹（等同于重新注册）"""
        return await self.enroll(speaker_id, audio, digit)
    
    async def delete(self, speaker_id: str) -> VoiceprintResult:
        """删除声纹"""
        try:
            voiceprint_file = self._voiceprint_file(speaker_id)
            
            if voiceprint_file.exists():
                voiceprint_file.unlink()
                logger.info(f"Deleted voiceprint for {speaker_id}")
                message = "删除成功"
            else:
                message = f"声纹不存在: {speaker_id}"
            
            return VoiceprintResult(
                success=True,
                score=0.0,
                decision=True,
                message=message,
                provider=self.get_provider_name()
            )
            
        except Exception as e:
            logger.error(f"Error deleting voiceprint: {e}")
            return VoiceprintResult(
                success=False,
                score=0.0,
                decision=False,
                message=f"删除失败: {str(e)}",
                provider=self.get_provider_name()
            )
