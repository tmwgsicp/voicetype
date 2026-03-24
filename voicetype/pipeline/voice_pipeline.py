#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Voice Typing core pipeline: ASR -> LLM intent restoration -> Text output.
"""

import asyncio
import logging
import time
from collections import deque
from typing import Optional, Callable, Awaitable

from openai import AsyncOpenAI

from ..context.scene_classifier import Scene, SCENES
from .intent_prompt import build_system_prompt
from .safety import pre_filter, post_validate

logger = logging.getLogger(__name__)

CONTEXT_WINDOW_SIZE = 20
CONTEXT_EXPIRE_S = 90.0


class VoiceTypingPipeline:
    """Orchestrates the voice typing flow:
    1. Receives ASR text (sentence-level)
    2. Classifies current scene
    3. Builds scene-aware prompt with recent context
    4. Sends to LLM for intent restoration
    5. Outputs cleaned text via callback
    """

    def __init__(
        self,
        llm_api_key: str,
        llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        llm_model: str = "qwen-turbo",
        llm_temperature: float = 0.3,
        llm_max_tokens: int = 200,
    ):
        self._client = AsyncOpenAI(
            api_key=llm_api_key,
            base_url=llm_base_url,
        )
        self._model = llm_model
        self._temperature = llm_temperature
        self._max_tokens = llm_max_tokens

        self._current_scene: Scene = SCENES["general"]
        self._rag_context: Optional[str] = None

        self._context_history: deque = deque(maxlen=CONTEXT_WINDOW_SIZE)

        self._on_raw_text: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_final_text: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_final_text_stream: Optional[Callable[[str], Awaitable[None]]] = None

    def set_scene(self, scene: Scene):
        self._current_scene = scene

    def set_rag_context(self, context: Optional[str]):
        self._rag_context = context

    def on_raw_text(self, callback: Callable[[str], Awaitable[None]]):
        self._on_raw_text = callback

    def on_final_text(self, callback: Callable[[str], Awaitable[None]]):
        self._on_final_text = callback

    def on_final_text_stream(self, callback: Callable[[str], Awaitable[None]]):
        self._on_final_text_stream = callback

    def _build_context_messages(self) -> list[dict]:
        now = time.time()
        messages = []
        for ts, asr_text, llm_result in self._context_history:
            if now - ts < CONTEXT_EXPIRE_S:
                messages.append({"role": "user", "content": asr_text})
                messages.append({"role": "assistant", "content": llm_result})
        return messages

    def clear_context(self):
        self._context_history.clear()

    async def process_asr_text(self, raw_text: str):
        """Process a complete ASR sentence through intent restoration."""
        if not raw_text or not raw_text.strip():
            return

        raw_text = raw_text.strip()
        logger.info("Processing ASR text: '%s' (scene=%s)", raw_text, self._current_scene.name)

        if self._on_raw_text:
            await self._on_raw_text(raw_text)

        safety = pre_filter(raw_text)

        system_prompt = build_system_prompt(
            scene=self._current_scene,
            rag_context=self._rag_context,
        )

        try:
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(self._build_context_messages())
            messages.append({"role": "user", "content": safety.text})

            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                stream=True,
                extra_body={
                    "chat_template_kwargs": {"enable_thinking": False}
                },
            )

            full_text = []
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    full_text.append(delta.content)
                    if self._on_final_text_stream:
                        await self._on_final_text_stream(delta.content)

            llm_output = "".join(full_text)

            result = post_validate(raw_text, llm_output, scene_name=self._current_scene.name)
            if result != llm_output:
                logger.warning("Safety L3 triggered, using fallback for: '%s'", raw_text[:80])

            logger.info("LLM result: '%s'", result)

            self._context_history.append((time.time(), raw_text, result))

            if self._on_final_text:
                await self._on_final_text(result)

        except Exception as e:
            logger.error("LLM processing failed: %s", e)
            if self._on_final_text:
                await self._on_final_text(raw_text)

    async def close(self):
        if self._client:
            await self._client.close()
