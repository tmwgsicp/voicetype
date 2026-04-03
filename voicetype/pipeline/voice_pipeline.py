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
from .rule_replacer import RuleReplacer, remove_lock_tags
from ..config import get_config_dir

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
        llm_base_url: str,
        llm_model: str,
        llm_temperature: float = 0.3,
        llm_max_tokens: int = 200,
    ):
        """
        Initialize VoiceTypingPipeline.
        
        Args:
            llm_api_key: LLM API key (required)
            llm_base_url: LLM API base URL (from config)
            llm_model: LLM model name (from config)
            llm_temperature: LLM temperature (from config, default: 0.3)
            llm_max_tokens: LLM max output tokens (from config, default: 200)
        """
        self._client = AsyncOpenAI(
            api_key=llm_api_key,
            base_url=llm_base_url,
        )
        self._model = llm_model
        self._temperature = llm_temperature
        self._max_tokens = llm_max_tokens

        self._current_scene: Scene = SCENES["general"]
        self._custom_prompt: Optional[str] = None  # 自定义场景提示词
        # REMOVED: self._rag_context - RAG feature not implemented

        self._context_history: deque = deque(maxlen=CONTEXT_WINDOW_SIZE)

        self._on_raw_text: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_final_text: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_final_text_stream: Optional[Callable[[str], Awaitable[None]]] = None
        
        # Rule replacer
        rules_file = get_config_dir() / "rules.json"
        self._rule_replacer = RuleReplacer(rules_file=rules_file)

    def set_scene(self, scene: Scene):
        self._current_scene = scene
    
    def set_custom_prompt(self, prompt: Optional[str]):
        """
        Set custom prompt for current scene.
        设置当前场景的自定义提示词。
        """
        self._custom_prompt = prompt

    # REMOVED: set_rag_context() - RAG feature not implemented

    def on_raw_text(self, callback: Callable[[str], Awaitable[None]]):
        self._on_raw_text = callback

    def on_final_text(self, callback: Callable[[str], Awaitable[None]]):
        self._on_final_text = callback

    def on_final_text_stream(self, callback: Callable[[str], Awaitable[None]]):
        self._on_final_text_stream = callback

    def _build_context_messages(self) -> list[dict]:
        """
        Build context messages.
        
        DISABLED: Context history causes LLM to treat this as a conversation
        and start "answering questions" instead of cleaning text.
        
        Example of the problem:
        - User says: "继续完成任务吧"
        - LLM responds: "好的。" (answering the "command")
        - Expected: "继续完成任务吧。" (cleaned text)
        
        Solution: Disable context until we find a way to prevent chatbot behavior.
        """
        return []  # Disable context to prevent chatbot behavior

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

        # Apply rule replacement BEFORE LLM processing
        text_after_rules = self._rule_replacer.apply(raw_text, add_lock_tags=True)
        
        safety = pre_filter(text_after_rules)

        system_prompt = build_system_prompt(
            scene=self._current_scene,
            custom_prompt=self._custom_prompt,
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
            
            # Remove lock tags from LLM output
            llm_output = remove_lock_tags(llm_output)

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
