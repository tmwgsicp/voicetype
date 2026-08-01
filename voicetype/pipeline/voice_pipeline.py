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
            llm_api_key: LLM API key (optional, 如果为空则跳过 LLM 处理)
            llm_base_url: LLM API base URL (from config)
            llm_model: LLM model name (from config)
            llm_temperature: LLM temperature (from config, default: 0.3)
            llm_max_tokens: LLM max output tokens (from config, default: 200)
        """
        self._llm_enabled = bool(llm_api_key and llm_api_key.strip())
        
        if self._llm_enabled:
            self._client = AsyncOpenAI(
                api_key=llm_api_key,
                base_url=llm_base_url,
            )
            self._model = llm_model
            self._temperature = llm_temperature
            self._max_tokens = llm_max_tokens
            logger.info("✓ LLM enabled: model=%s, base_url=%s", llm_model, llm_base_url)
        else:
            self._client = None
            logger.warning("✗ LLM disabled: API Key not configured (will output raw ASR text directly)")

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

        # 顺序很关键：先对「原始文本」做安全过滤（它会剥离用户输入里的 <lock> 标签，防注入），
        # 再套用术语规则加上锁定标签，最后带着锁定标签发给 LLM。
        # 若顺序反过来，pre_filter 会把规则刚加的锁定标签删掉，导致术语锁定完全失效。
        safety = pre_filter(raw_text)
        text_after_rules = self._rule_replacer.apply(safety.text, add_lock_tags=True)

        # 如果 LLM 未启用，直接输出规则替换后的文本
        if not self._llm_enabled:
            # 移除锁定标签（用户不应该看到）
            final_text = remove_lock_tags(text_after_rules)
            logger.info("LLM disabled, outputting rule-replaced text: '%s'", final_text)
            if self._on_final_text:
                await self._on_final_text(final_text)
            return

        system_prompt = build_system_prompt(
            scene=self._current_scene,
            custom_prompt=self._custom_prompt,
        )

        try:
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(self._build_context_messages())
            # 带锁定标签发给 LLM（系统提示词要求 100% 保留 <lock> 内容）
            messages.append({"role": "user", "content": text_after_rules})

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
            # LLM 失败时输出规则替换后的文本
            final_text = remove_lock_tags(text_after_rules)
            if self._on_final_text:
                await self._on_final_text(final_text)

    async def apply_text_action(self, selection: str, system_prompt: str) -> str:
        """
        预设文本动作：用固定的 system_prompt 改写选中的原文，返回改写后的最终文本。
        selection = 用户选中的原文；system_prompt = 某个预设动作的固定 prompt（见 text_actions.py）。
        失败或未配 LLM 时原样返回选区，绝不吞掉用户文字。
        """
        selection = (selection or "").strip()
        if not selection:
            return selection
        if not self._llm_enabled or not self._client:
            # 没配 LLM 无法改写，原样返回
            logger.warning("apply_text_action: LLM not configured, returning selection unchanged")
            return selection
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": selection},
                ],
                temperature=0.3,
                max_tokens=max(self._max_tokens, len(selection) + 256),
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            out = (resp.choices[0].message.content or "").strip()
            logger.info("Text action: '%s' -> '%s'", selection[:40], out[:60])
            return out or selection
        except Exception as e:
            logger.error("Text action failed: %s", e)
            return selection

    async def compose_reply(self, context: str, intent: str, tone: str = "auto") -> str:
        """
        地道回复助手：结合【对方消息=上下文】和【你的意图】，生成一条地道、贴合语气的英文回复。
        context 可为空（纯从意图生成）；intent 可中文/粗英文。返回英文回复本身。
        """
        context = (context or "").strip()
        intent = (intent or "").strip()
        if not intent and not context:
            return ""
        if not self._llm_enabled or not self._client:
            logger.warning("compose_reply: LLM not configured")
            return ""

        tone_map = {
            "casual": "语气偏轻松随意（像 Slack 上和同事聊），可用缩写、口语连接词。",
            "professional": "语气偏正式、专业、得体（适合正式邮件或与上级/客户），但不僵硬、不浮夸。",
            "warm": "语气友好、热情、有人情味，但仍专业。",
            "auto": "自动判断：仔细读上下文的语气和正式度，让回复与之匹配（对方随意你就随意，对方正式你就正式）。",
        }
        tone_instr = tone_map.get(tone, tone_map["auto"])

        system_prompt = (
            "你是帮助非英语母语者在国际远程团队里回复工作消息的助手（场景如 Slack、Teams、邮件）。"
            "用户会给你【对方消息】(要回复的上下文，可能为空) 和【我的意图】(用户想表达什么，可能是中文或蹩脚英文)。"
            "你要写出一条**英文回复**，要求：\n"
            "1. 像英语母语的职场人自然写出来的——地道、流畅，用缩写和自然的连接词，绝不逐字直译、不生硬、不机械。\n"
            "2. 贴合【对方消息】的语气和正式度；" + tone_instr + "\n"
            "3. 简洁、直奔重点，不要多余寒暄或解释（除非上下文里那样才自然）。\n"
            "4. 准确传达【我的意图】，并让它自然衔接对话。\n"
            "只输出这条英文回复本身，不要解释、不要加引号、不要任何多余内容。"
        )
        user_msg = (
            f"【对方消息】\n{context if context else '(无，直接根据我的意图写)'}\n\n"
            f"【我的意图】\n{intent if intent else '(无，请根据上下文给出合适的回复)'}"
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.6,  # 回复要自然，给一点发挥空间
                max_tokens=max(self._max_tokens, 512),
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            out = (resp.choices[0].message.content or "").strip()
            logger.info("Reply composed: ctx=%d intent='%s' -> '%s'", len(context), intent[:40], out[:80])
            return out
        except Exception as e:
            logger.error("compose_reply failed: %s", e)
            return ""

    async def close(self):
        if self._client:
            await self._client.close()
