#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""Usage statistics API for the Web UI."""

import logging

from fastapi import APIRouter

from .. import stats

logger = logging.getLogger(__name__)

stats_router = APIRouter(prefix="/api/stats")


@stats_router.get("/summary")
async def get_summary():
    """Totals, today/week, streak, and estimated typing time."""
    return stats.get_summary()


@stats_router.get("/daily")
async def get_daily(days: int = 30):
    """Per-day char/dictation counts for the last N days (zero-filled)."""
    days = max(1, min(days, 365))
    return {"days": stats.get_daily(days)}


@stats_router.get("/scenes")
async def get_scenes():
    """Char totals grouped by scene."""
    return {"scenes": stats.get_scene_breakdown()}


@stats_router.get("/history")
async def get_history(limit: int = 50, offset: int = 0, q: str = ""):
    """听写历史（最新在前），可关键词搜索。"""
    return {"items": stats.get_history(limit=limit, offset=offset, query=(q or None))}


@stats_router.delete("/history/{item_id}")
async def delete_history_item(item_id: int):
    """删除单条历史（保留统计计数）。"""
    return {"success": stats.delete_history_item(item_id)}


@stats_router.post("/history/clear")
async def clear_history():
    """清空全部历史原文（统计不受影响）。"""
    return {"success": stats.clear_history()}
