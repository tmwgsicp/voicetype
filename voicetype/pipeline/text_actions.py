#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
预设文本动作（Preset Text Actions）。

选中文字 → 按编辑快捷键 → 弹出菜单 → 点一个预设动作 → LLM 按固定 prompt 改写 → 替换选区。

预设可编辑：用户在设置里增删改的动作存进 config.text_actions（单一真源）。
config 为空时回落到这里的 DEFAULT_ACTIONS。本模块只做「对任意动作列表求菜单视图 / 求 prompt」，
不持有状态——engine 持有当前生效的列表（来自 config），随配置热更新。

每个动作字段：id / label / hint / prompt。菜单顺序 = 列表顺序。
"""

import re
from typing import Optional

# 所有动作共用的输出纪律，拼到每个 prompt 后面，保证结果可直接上屏。
OUTPUT_RULE = (
    "\n\n严格要求：只输出改写后的最终文本本身；"
    "不要解释、不要加引号、不要加前后缀、不要重复原文或说明你做了什么。"
)

# 内置默认预设（config.text_actions 为空时使用）。
DEFAULT_ACTIONS = [
    {
        "id": "translate",
        "label": "翻译",
        "hint": "中英互译",
        "prompt": (
            "你是翻译助手。把下面的文本翻译成另一种语言："
            "如果原文是中文就翻成地道的英文；如果原文是英文（或其它外语）就翻成自然的简体中文。"
            "保持原意、语气和专业术语的准确，不要漏译或增译。"
        ),
    },
    {
        "id": "polish",
        "label": "润色",
        "hint": "更通顺自然",
        "prompt": (
            "你是中文/英文写作润色助手。在保持原意和原语言不变的前提下，"
            "把下面的文本改得更通顺、自然、地道，去掉口语赘词和重复，但不要改变意思、不要扩写。"
        ),
    },
    {
        "id": "concise",
        "label": "精简",
        "hint": "更短更利落",
        "prompt": (
            "你是精简助手。在保留全部关键信息和原语言的前提下，"
            "把下面的文本改写得更短、更利落，删掉冗余和啰嗦，但不要丢失重要事实。"
        ),
    },
    {
        "id": "formal",
        "label": "正式",
        "hint": "更书面礼貌",
        "prompt": (
            "你是公文/邮件写作助手。保持原意和原语言不变，"
            "把下面的文本改写得更正式、书面、礼貌得体，适合正式场合或商务邮件，但不要浮夸。"
        ),
    },
    {
        "id": "bullets",
        "label": "要点",
        "hint": "改成条目",
        "prompt": (
            "你是内容整理助手。保持原语言不变，"
            "把下面的文本重新组织成清晰的要点列表：每行一个要点，行首用「- 」，"
            "合并同类信息、去掉口语赘述，但不要遗漏关键内容、不要编造原文没有的信息。"
        ),
    },
]


def _slugify(label: str, idx: int) -> str:
    """从 label 生成一个稳定 id；生成不出就用 action{idx}。"""
    s = re.sub(r"[^a-z0-9]+", "-", (label or "").strip().lower()).strip("-")
    return s or f"action{idx}"


def normalize_actions(raw) -> list[dict]:
    """把来自 config 的原始列表清洗成合法动作列表。

    - 为空 / 非法 → 返回 DEFAULT_ACTIONS 的拷贝。
    - 丢弃缺 label 或 prompt 的项；缺 id 的自动生成；保证 id 唯一。
    """
    if not raw or not isinstance(raw, list):
        return [dict(a) for a in DEFAULT_ACTIONS]

    out: list[dict] = []
    seen_ids: set[str] = set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        prompt = str(item.get("prompt", "")).strip()
        if not label or not prompt:
            continue
        aid = str(item.get("id", "")).strip() or _slugify(label, i)
        # 去重
        base, n = aid, 2
        while aid in seen_ids:
            aid = f"{base}-{n}"
            n += 1
        seen_ids.add(aid)
        out.append({
            "id": aid,
            "label": label,
            "hint": str(item.get("hint", "")).strip(),
            "prompt": prompt,
        })

    if not out:
        return [dict(a) for a in DEFAULT_ACTIONS]
    return out


def menu_view(actions: list[dict]) -> list[dict]:
    """给前端菜单用的精简列表（不含 prompt）。"""
    return [
        {"id": a["id"], "label": a["label"], "hint": a.get("hint", "")}
        for a in actions
    ]


def prompt_for(actions: list[dict], action_id: str) -> Optional[str]:
    """取某动作拼好输出纪律后的完整 system prompt；找不到返回 None。"""
    for a in actions:
        if a["id"] == action_id:
            return a["prompt"] + OUTPUT_RULE
    return None
