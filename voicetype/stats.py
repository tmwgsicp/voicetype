#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Usage statistics for VoiceType (SQLite-backed).

Records one row per finalized dictation (chars/words/scene/app/timestamp) and
provides aggregations for the stats UI: totals, today/week, per-day history,
per-scene breakdown, and streak. Storage lives in the per-OS config dir so it
persists across upgrades.
"""

import logging
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from .config import get_config_dir

logger = logging.getLogger(__name__)

DB_PATH = get_config_dir() / "stats.db"

# 手动打字的估算速度（字符/分钟），用于估算"省下的打字时间"。
# 中文拼音输入普遍约 150-250 cpm，取 200 作为保守估算。
TYPING_CHARS_PER_MIN = 200

_lock = threading.Lock()
_CJK = r"一-鿿぀-ヿ가-힯"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dictations (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            ts    REAL NOT NULL,        -- unix timestamp
            day   TEXT NOT NULL,        -- local date YYYY-MM-DD
            chars INTEGER NOT NULL,     -- non-whitespace character count
            words INTEGER NOT NULL,     -- CJK chars + latin/number tokens
            scene TEXT,
            app   TEXT,
            text  TEXT                  -- 听写原文（用于历史；清历史时置空但保留统计）
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dictations_day ON dictations(day)")
    # 兼容旧库：老版本没有 text 列，补上
    cols = [r[1] for r in conn.execute("PRAGMA table_info(dictations)").fetchall()]
    if "text" not in cols:
        conn.execute("ALTER TABLE dictations ADD COLUMN text TEXT")
    return conn


def count_chars(text: str) -> int:
    """Non-whitespace character count (中文按字计)."""
    return len(re.sub(r"\s+", "", text or ""))


def count_words(text: str) -> int:
    """CJK chars each count as one word; latin/number runs count as one word each."""
    if not text:
        return 0
    cjk = len(re.findall(f"[{_CJK}]", text))
    latin = len(re.findall(r"[A-Za-z0-9]+", text))
    return cjk + latin


def record_dictation(text: str, scene: Optional[str] = None, app: Optional[str] = None) -> None:
    """Record one finalized dictation. Never raises (stats must not break dictation)."""
    text = (text or "").strip()
    if not text:
        return
    chars = count_chars(text)
    words = count_words(text)
    if chars == 0:
        return
    now = time.time()
    day = datetime.now().strftime("%Y-%m-%d")
    try:
        with _lock:
            conn = _get_conn()
            try:
                conn.execute(
                    "INSERT INTO dictations (ts, day, chars, words, scene, app, text) VALUES (?,?,?,?,?,?,?)",
                    (now, day, chars, words, scene, app, text),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception as e:
        logger.warning("Failed to record dictation stat: %s", e)


def _scalar(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return (row[0] if row and row[0] is not None else 0)


def get_summary() -> dict:
    """Aggregate totals for the stats dashboard."""
    today = datetime.now().strftime("%Y-%m-%d")
    week_start = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    try:
        with _lock:
            conn = _get_conn()
            try:
                total_chars = _scalar(conn, "SELECT SUM(chars) FROM dictations")
                total_words = _scalar(conn, "SELECT SUM(words) FROM dictations")
                total_count = _scalar(conn, "SELECT COUNT(*) FROM dictations")
                today_chars = _scalar(conn, "SELECT SUM(chars) FROM dictations WHERE day=?", (today,))
                today_count = _scalar(conn, "SELECT COUNT(*) FROM dictations WHERE day=?", (today,))
                week_chars = _scalar(conn, "SELECT SUM(chars) FROM dictations WHERE day>=?", (week_start,))
                first_ts = _scalar(conn, "SELECT MIN(ts) FROM dictations")
                active_days = [r[0] for r in conn.execute(
                    "SELECT DISTINCT day FROM dictations ORDER BY day DESC"
                ).fetchall()]
            finally:
                conn.close()
    except Exception as e:
        logger.warning("Failed to read stats summary: %s", e)
        return _empty_summary()

    return {
        "total_chars": int(total_chars),
        "total_words": int(total_words),
        "total_dictations": int(total_count),
        "today_chars": int(today_chars),
        "today_dictations": int(today_count),
        "week_chars": int(week_chars),
        "streak_days": _compute_streak(active_days),
        "active_days": len(active_days),
        "est_typing_minutes": round(total_chars / TYPING_CHARS_PER_MIN, 1),
        "first_use": datetime.fromtimestamp(first_ts).strftime("%Y-%m-%d") if first_ts else None,
    }


def get_daily(days: int = 30) -> list:
    """Per-day char/count for the last N days (oldest first), zero-filled."""
    start = datetime.now() - timedelta(days=days - 1)
    try:
        with _lock:
            conn = _get_conn()
            try:
                rows = conn.execute(
                    "SELECT day, SUM(chars), COUNT(*) FROM dictations WHERE day>=? GROUP BY day",
                    (start.strftime("%Y-%m-%d"),),
                ).fetchall()
            finally:
                conn.close()
    except Exception as e:
        logger.warning("Failed to read daily stats: %s", e)
        rows = []
    by_day = {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in rows}
    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        chars, count = by_day.get(d, (0, 0))
        out.append({"day": d, "chars": chars, "dictations": count})
    return out


def get_scene_breakdown() -> list:
    """Char totals grouped by scene, most-used first."""
    try:
        with _lock:
            conn = _get_conn()
            try:
                rows = conn.execute(
                    "SELECT COALESCE(scene,'general'), SUM(chars), COUNT(*) "
                    "FROM dictations GROUP BY scene ORDER BY SUM(chars) DESC"
                ).fetchall()
            finally:
                conn.close()
    except Exception as e:
        logger.warning("Failed to read scene stats: %s", e)
        rows = []
    return [{"scene": r[0], "chars": int(r[1] or 0), "dictations": int(r[2] or 0)} for r in rows]


def get_history(limit: int = 50, offset: int = 0, query: Optional[str] = None) -> list:
    """
    返回听写历史（有原文的记录，最新在前）。可选关键词搜索。
    历史与统计共用一张表——已"删除"的历史记录 text 被置空，但统计计数仍保留。
    """
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    try:
        with _lock:
            conn = _get_conn()
            try:
                base = ("SELECT id, ts, text, scene, app, chars FROM dictations "
                        "WHERE text IS NOT NULL AND text != ''")
                params: list = []
                if query:
                    base += " AND text LIKE ?"
                    params.append(f"%{query}%")
                base += " ORDER BY ts DESC LIMIT ? OFFSET ?"
                params += [limit, offset]
                rows = conn.execute(base, params).fetchall()
            finally:
                conn.close()
    except Exception as e:
        logger.warning("Failed to read history: %s", e)
        rows = []
    return [
        {
            "id": r[0],
            "ts": r[1],
            "time": datetime.fromtimestamp(r[1]).strftime("%Y-%m-%d %H:%M"),
            "text": r[2] or "",
            "scene": r[3],
            "app": r[4],
            "chars": r[5],
        }
        for r in rows
    ]


def delete_history_item(item_id: int) -> bool:
    """删除单条历史（置空原文，保留统计计数）。"""
    try:
        with _lock:
            conn = _get_conn()
            try:
                conn.execute("UPDATE dictations SET text=NULL WHERE id=?", (item_id,))
                conn.commit()
            finally:
                conn.close()
        return True
    except Exception as e:
        logger.warning("Failed to delete history item: %s", e)
        return False


def clear_history() -> bool:
    """清空全部历史原文（统计数字不受影响）。"""
    try:
        with _lock:
            conn = _get_conn()
            try:
                conn.execute("UPDATE dictations SET text=NULL")
                conn.commit()
            finally:
                conn.close()
        return True
    except Exception as e:
        logger.warning("Failed to clear history: %s", e)
        return False


def _compute_streak(active_days_desc: list) -> int:
    """Consecutive-day streak ending today or yesterday."""
    if not active_days_desc:
        return 0
    days = set(active_days_desc)
    today = datetime.now().date()
    # Streak counts only if used today or yesterday (grace for not-yet-used-today).
    if today.strftime("%Y-%m-%d") not in days and \
       (today - timedelta(days=1)).strftime("%Y-%m-%d") not in days:
        return 0
    streak = 0
    cursor = today
    if today.strftime("%Y-%m-%d") not in days:
        cursor = today - timedelta(days=1)
    while cursor.strftime("%Y-%m-%d") in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _empty_summary() -> dict:
    return {
        "total_chars": 0, "total_words": 0, "total_dictations": 0,
        "today_chars": 0, "today_dictations": 0, "week_chars": 0,
        "streak_days": 0, "active_days": 0, "est_typing_minutes": 0.0, "first_use": None,
    }
