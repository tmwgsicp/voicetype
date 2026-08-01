#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
文本编辑动作 API。

选中文字 → 编辑快捷键 → 后端广播 edit_menu_show → 前端菜单窗弹出 →
用户选动作 → POST /api/edit/apply → 后端切回目标程序改写替换。
菜单动作清单从后端拉取（单一真源，见 text_actions.py）。
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from ..pipeline.text_actions import menu_view, normalize_actions, DEFAULT_ACTIONS

logger = logging.getLogger(__name__)

edit_router = APIRouter(prefix="/api/edit")

_engine = None


def set_engine(engine):
    global _engine
    _engine = engine


@edit_router.get("/actions")
async def get_actions():
    """返回当前生效的预设动作清单（菜单视图，供前端菜单渲染）。"""
    if _engine:
        return {"actions": _engine.get_menu_actions()}
    return {"actions": menu_view(normalize_actions(None))}


@edit_router.get("/actions/full")
async def get_actions_full():
    """返回完整动作（含 prompt，供设置页编辑）；同时给出内置默认供「恢复默认」。"""
    actions = normalize_actions(_engine._text_actions if _engine else None)
    return {"actions": actions, "defaults": [dict(a) for a in DEFAULT_ACTIONS]}


class ApplyRequest(BaseModel):
    action: str


@edit_router.post("/apply")
async def apply_action(req: ApplyRequest):
    """套用某个预设动作到当前选区。"""
    if not _engine:
        return {"status": "error", "message": "engine not ready"}
    await _engine.apply_edit_action(req.action)
    return {"status": "ok"}


@edit_router.post("/cancel")
async def cancel():
    """取消编辑，收起菜单。"""
    if not _engine:
        return {"status": "error", "message": "engine not ready"}
    await _engine.cancel_edit()
    return {"status": "ok"}


class ReplyRequest(BaseModel):
    context: str = ""
    intent: str = ""
    tone: str = "auto"


@edit_router.post("/reply")
async def compose_reply(req: ReplyRequest):
    """地道回复：结合上下文+意图生成英文回复。"""
    if not _engine:
        return {"status": "error", "message": "engine not ready"}
    reply = await _engine.pipeline.compose_reply(req.context, req.intent, req.tone)
    if not reply:
        return {"status": "error", "message": "生成失败，请检查 LLM 配置", "reply": ""}
    return {"status": "ok", "reply": reply}


@edit_router.post("/reply/cancel")
async def reply_cancel():
    """关闭回复助手窗口。"""
    if not _engine:
        return {"status": "error", "message": "engine not ready"}
    await _engine.cancel_reply()
    return {"status": "ok"}
