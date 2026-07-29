#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
预设文本动作（Preset Text Actions）。

选中文字 → 按编辑快捷键 → 弹出菜单 → 选一个预设动作 → LLM 按固定 prompt 改写 → 替换选区。

设计取自成熟竞品的共识：
- superwhisper「Modes」：固定 prompt 的可预测变换，不让 LLM 猜自由指令。
- 每个动作只输出「改写后的最终文本」，不解释、不加引号，方便直接粘贴替换。

这是单一真源：菜单顺序、快捷数字键、prompt 全部在这里定义，
前端菜单通过 /api/edit/actions 拉取，避免前后端各写一份。
"""

from typing import Optional

# 所有动作共用的输出纪律，拼到每个 prompt 后面，保证结果可直接上屏。
_OUTPUT_RULE = (
    "\n\n严格要求：只输出改写后的最终文本本身；"
    "不要解释、不要加引号、不要加前后缀、不要重复原文或说明你做了什么。"
)

# 顺序 = 菜单顺序 = 数字键顺序（key 为 1..5）。
TEXT_ACTIONS = [
    {
        "id": "translate",
        "label": "翻译",
        "hint": "中英互译",
        "key": "1",
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
        "key": "2",
        "prompt": (
            "你是中文/英文写作润色助手。在保持原意和原语言不变的前提下，"
            "把下面的文本改得更通顺、自然、地道，去掉口语赘词和重复，但不要改变意思、不要扩写。"
        ),
    },
    {
        "id": "concise",
        "label": "精简",
        "hint": "更短更利落",
        "key": "3",
        "prompt": (
            "你是精简助手。在保留全部关键信息和原语言的前提下，"
            "把下面的文本改写得更短、更利落，删掉冗余和啰嗦，但不要丢失重要事实。"
        ),
    },
    {
        "id": "formal",
        "label": "正式",
        "hint": "更书面礼貌",
        "key": "4",
        "prompt": (
            "你是公文/邮件写作助手。保持原意和原语言不变，"
            "把下面的文本改写得更正式、书面、礼貌得体，适合正式场合或商务邮件，但不要浮夸。"
        ),
    },
    {
        "id": "bullets",
        "label": "要点",
        "hint": "改成条目",
        "key": "5",
        "prompt": (
            "你是内容整理助手。保持原语言不变，"
            "把下面的文本重新组织成清晰的要点列表：每行一个要点，行首用「- 」，"
            "合并同类信息、去掉口语赘述，但不要遗漏关键内容、不要编造原文没有的信息。"
        ),
    },
]

_BY_ID = {a["id"]: a for a in TEXT_ACTIONS}


def get_action(action_id: str) -> Optional[dict]:
    """按 id 取动作定义（含 prompt）。找不到返回 None。"""
    return _BY_ID.get(action_id)


def action_prompt(action_id: str) -> Optional[str]:
    """取某动作拼好输出纪律后的完整 system prompt。"""
    a = _BY_ID.get(action_id)
    if not a:
        return None
    return a["prompt"] + _OUTPUT_RULE


def actions_for_menu() -> list[dict]:
    """给前端菜单用的精简列表（不含 prompt）。"""
    return [
        {"id": a["id"], "label": a["label"], "hint": a["hint"], "key": a["key"]}
        for a in TEXT_ACTIONS
    ]
