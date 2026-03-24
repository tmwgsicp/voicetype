#!/usr/bin/env python3
# Copyright (C) 2026 VoiceForge Contributors
# Licensed under AGPL-3.0

"""RAG 知识库检索扩展（本地 Embedding 模型版本）

使用本地 sentence-transformers 模型进行 Embedding，大幅降低延迟。
通过 HTTP 连接本地或远程 Qdrant 服务器进行向量检索。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional
import time

from voicetype.voiceforge.core.extension import Extension, ExtensionMeta, Port, PortType
from voicetype.voiceforge.core.config import ExtensionConfig
from pydantic import Field

logger = logging.getLogger(__name__)

# BGE model local directory (relative to project root)
_MODEL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "models"


def _resolve_model_path(model_name: str) -> str:
    """
    Resolve embedding model path with priority:
    1. Local models/ directory (for offline / packaged deployment)
    2. HuggingFace Hub (with hf-mirror.com support via HF_ENDPOINT env var)
    """
    # e.g. "BAAI/bge-small-zh-v1.5" -> "models/bge-small-zh-v1.5"
    local_name = model_name.split("/")[-1] if "/" in model_name else model_name
    local_path = _MODEL_DIR / local_name

    if local_path.exists() and (local_path / "config.json").exists():
        logger.info("Using local model: %s", local_path)
        return str(local_path)

    # Set HuggingFace mirror for users in China if not already set
    import os
    if not os.environ.get("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        logger.info("HF_ENDPOINT not set, using mirror: hf-mirror.com")

    logger.info("Model not found locally at %s, downloading from HuggingFace...", local_path)
    return model_name


class RAGLocalConfig(ExtensionConfig):
    """RAG 本地 Qdrant 配置"""
    
    embedding_model: str = Field(
        default="BAAI/bge-small-zh-v1.5",
        description="本地 Embedding 模型名称"
    )
    embedding_normalize: bool = Field(
        default=True,
        description="是否归一化向量"
    )
    
    qdrant_url: str = Field(default="localhost", description="Qdrant URL")
    qdrant_port: int = Field(default=6333, description="Qdrant 端口")
    qdrant_api_key: str = Field(default="", description="Qdrant API Key (Cloud)")
    qdrant_collection_name: str = Field(default="voicetype-kb", description="Qdrant 集合名称")
    qdrant_https: bool = Field(default=False, description="是否使用 HTTPS")
    
    top_k: int = Field(default=3, ge=1, le=10, description="返回 Top-K 结果")
    score_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="相似度阈值")


class RAGLocalExtension(Extension[RAGLocalConfig]):
    """RAG 知识库检索（本地 Embedding 模型）"""
    
    config_class = RAGLocalConfig
    
    metadata = ExtensionMeta(
        name="rag_local",
        description="RAG 知识库向量检索（本地 Embedding）",
        category="rag",
    )
    input_ports = [
        Port("user_text", PortType.TEXT, "用户查询文本"),
    ]
    output_ports = [
        Port("user_text", PortType.TEXT, "透传用户文本给 LLM"),
        Port("rag_context", PortType.TEXT, "检索到的知识库上下文"),
    ]

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._model = None
        self._qdrant_client = None
        self._top_k: int = self.config.top_k
        self._score_threshold: float = self.config.score_threshold
        self._shared_model = None
        self._shared_qdrant_client = None
        self._use_shared = False
    
    def set_shared_resources(self, model, qdrant_client=None):
        """设置共享资源（从连接池注入）"""
        self._shared_model = model
        self._shared_qdrant_client = qdrant_client
        self._use_shared = True
        
        if qdrant_client:
            logger.info(f"[{self.config.name}] 使用全局共享 RAG 资源")
        else:
            logger.warning(f"[{self.config.name}] Qdrant 客户端未提供")

    async def _do_start(self):
        self._running = True
        
        if self._use_shared and self._shared_model and self._shared_qdrant_client:
            self._model = self._shared_model
            self._qdrant_client = self._shared_qdrant_client
            logger.info(f"[{self.config.name}] RAG 使用全局共享资源")
            return

        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading local embedding model: {self.config.embedding_model}")
            load_start = time.time()

            def _load_model():
                model_name = self.config.embedding_model
                model_path = _resolve_model_path(model_name)
                logger.info("Loading model from: %s", model_path)
                model = SentenceTransformer(model_path, device="cpu")
                model.encode("warmup", normalize_embeddings=self.config.embedding_normalize)
                return model

            self._model = await asyncio.get_event_loop().run_in_executor(None, _load_model)

            load_time = (time.time() - load_start) * 1000
            logger.info(f"Embedding model loaded + warmup in {load_time:.1f}ms")
            logger.info(f"  Model: {self.config.embedding_model}")
            logger.info(f"  Dimensions: {self._model.get_sentence_embedding_dimension()}")
            
        except ImportError:
            logger.error("sentence-transformers not installed: pip install sentence-transformers")
            self._model = None
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self._model = None

        if not self.config.qdrant_url or not self.config.qdrant_collection_name:
            logger.error("RAG: Qdrant not configured")
            return

        try:
            from qdrant_client import QdrantClient

            if self.config.qdrant_api_key:
                logger.info(f"Connecting Qdrant Cloud: {self.config.qdrant_url}")
                self._qdrant_client = QdrantClient(
                    url=self.config.qdrant_url,
                    api_key=self.config.qdrant_api_key
                )
            else:
                qdrant_url = f"http://{self.config.qdrant_url}:{self.config.qdrant_port}"
                logger.info(f"Connecting Qdrant: {qdrant_url}")
                self._qdrant_client = QdrantClient(url=qdrant_url)
            
            logger.info(f"RAG ready (collection: {self.config.qdrant_collection_name})")
            
            if self._model:
                try:
                    warmup_query_start = time.time()
                    warmup_vector = await self._embed("warmup query")
                    _ = self._qdrant_client.search(
                        collection_name=self.config.qdrant_collection_name,
                        query_vector=warmup_vector,
                        limit=1
                    )
                    warmup_query_time = (time.time() - warmup_query_start) * 1000
                    logger.info(f"Qdrant index warmup done in {warmup_query_time:.1f}ms")
                except Exception as e:
                    logger.warning(f"Qdrant warmup failed (non-fatal): {e}")
                
        except Exception as e:
            logger.error(f"Qdrant connection failed: {e}")
            self._qdrant_client = None

    async def on_data(self, port: str, data: Any):
        if port != "user_text" or not isinstance(data, str) or not data.strip():
            return

        user_text = data.strip()
        await self.send("user_text", user_text)
        asyncio.create_task(self._retrieve_and_send(user_text))

    async def _embed(self, text: str) -> list[float]:
        """生成 Embedding（在线程池中运行以避免阻塞）"""
        if not self._model:
            raise RuntimeError("Embedding model not loaded")
        
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: self._model.encode(
                text,
                normalize_embeddings=self.config.embedding_normalize
            )
        )
        return embedding.tolist()

    async def _retrieve(self, query: str) -> Optional[str]:
        if not self._model or not self._qdrant_client:
            return None

        try:
            embed_start = time.time()
            vector = await self._embed(query)
            embed_time = (time.time() - embed_start) * 1000
            
            query_start = time.time()
            results = self._qdrant_client.search(
                collection_name=self.config.qdrant_collection_name,
                query_vector=vector,
                limit=self._top_k
            )
            query_time = (time.time() - query_start) * 1000
            
            relevant = []
            top_score = results[0].score if results else 0.0
            for match in results:
                if match.score >= self._score_threshold:
                    text = match.payload.get("text", "")
                    if text:
                        relevant.append(text)
            
            total_time = embed_time + query_time
            if not relevant:
                logger.info(
                    "RAG miss (query=%s, top_score=%.3f, threshold=%.2f, "
                    "embed=%.1fms, search=%.1fms)",
                    query[:30], top_score, self._score_threshold,
                    embed_time, query_time,
                )
                return None
            
            logger.info(
                "RAG hit %d (query=%s, top_score=%.3f, "
                "total=%.1fms)",
                len(relevant), query[:30], top_score, total_time,
            )
            return "\n\n---\n\n".join(relevant)

        except Exception as e:
            logger.warning(f"RAG retrieval error: {e}")
            return None
    
    async def _retrieve_and_send(self, user_text: str):
        """异步检索并发送 RAG 上下文"""
        context = await self._retrieve(user_text)
        if context:
            await self.send("rag_context", context)

    async def _do_stop(self):
        self._running = False
        if self._qdrant_client and not self._use_shared:
            try:
                self._qdrant_client.close()
            except Exception:
                pass
            self._qdrant_client = None
        if not self._use_shared:
            self._model = None
        logger.info("RAG stopped")
