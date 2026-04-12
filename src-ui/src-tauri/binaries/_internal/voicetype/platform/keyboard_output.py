#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Text output via clipboard paste (Windows/macOS) or pynput typing (fallback).
Clipboard paste is fast and compatible with CJK + English mixed text.
"""

import asyncio
import logging
import sys
from typing import List, Optional

logger = logging.getLogger(__name__)

_pynput_controller = None
_pynput_Key = None


def _ensure_pynput():
    global _pynput_controller, _pynput_Key
    if _pynput_controller is None:
        from pynput.keyboard import Controller, Key
        _pynput_controller = Controller()
        _pynput_Key = Key


_win32_ready = False


def _init_win32():
    """Set up ctypes function signatures once (critical for 64-bit)."""
    global _win32_ready
    if _win32_ready:
        return
    
    # macOS没有ctypes.wintypes,必须在函数内导入
    if sys.platform != "win32":
        logger.warning("_init_win32 called on non-Windows platform, skipping")
        return
    
    import ctypes
    import ctypes.wintypes as w

    k32 = ctypes.windll.kernel32
    u32 = ctypes.windll.user32

    k32.GlobalAlloc.argtypes = [w.UINT, ctypes.c_size_t]
    k32.GlobalAlloc.restype = ctypes.c_void_p

    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalLock.restype = ctypes.c_void_p

    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.restype = w.BOOL

    k32.GlobalFree.argtypes = [ctypes.c_void_p]
    k32.GlobalFree.restype = ctypes.c_void_p

    u32.OpenClipboard.argtypes = [w.HWND]
    u32.OpenClipboard.restype = w.BOOL

    u32.CloseClipboard.argtypes = []
    u32.CloseClipboard.restype = w.BOOL

    u32.EmptyClipboard.argtypes = []
    u32.EmptyClipboard.restype = w.BOOL

    u32.SetClipboardData.argtypes = [w.UINT, ctypes.c_void_p]
    u32.SetClipboardData.restype = ctypes.c_void_p

    _win32_ready = True


def _clipboard_paste_win32(text: str) -> bool:
    """Windows: write text to clipboard via Win32 API, then simulate Ctrl+V."""
    import ctypes
    import time

    logger.info("Clipboard paste START: %d chars: '%s'", len(text), text)
    _init_win32()

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    VK_CONTROL = 0x11
    VK_V = 0x56
    KEYEVENTF_KEYUP = 0x0002

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    opened = False
    for attempt in range(10):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.03)

    if not opened:
        logger.warning("Failed to open clipboard after 10 retries")
        return False

    logger.debug("Clipboard opened successfully")

    try:
        user32.EmptyClipboard()

        data = text.encode("utf-16-le") + b"\x00\x00"
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h_mem:
            logger.warning("GlobalAlloc failed")
            return False

        ptr = kernel32.GlobalLock(h_mem)
        if not ptr:
            logger.warning("GlobalLock failed")
            kernel32.GlobalFree(h_mem)
            return False

        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(h_mem)

        result = user32.SetClipboardData(CF_UNICODETEXT, h_mem)
        if not result:
            logger.warning("SetClipboardData failed")
            kernel32.GlobalFree(h_mem)
            return False
        logger.info("SetClipboardData success, data length: %d bytes", len(data))
    finally:
        user32.CloseClipboard()

    time.sleep(0.12)  # 增加到120ms，确保剪切板完全写入

    logger.info("Simulating Ctrl+V...")
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.01)
    user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.03)  # 增加按键间隔
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.01)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    time.sleep(0.1)  # 增加等待时间
    logger.info("Ctrl+V completed")
    return True


def _clipboard_paste_darwin(text: str) -> bool:
    """macOS: write text to clipboard via pbcopy, then simulate Cmd+V."""
    import subprocess
    import time

    try:
        proc = subprocess.run(
            ["pbcopy"],
            input=text.encode("utf-8"),
            timeout=2,
        )
        if proc.returncode != 0:
            logger.warning("pbcopy failed with returncode %d", proc.returncode)
            return False
    except Exception as e:
        logger.warning("pbcopy failed: %s", e)
        return False

    time.sleep(0.03)

    _ensure_pynput()
    _pynput_controller.press(_pynput_Key.cmd)
    _pynput_controller.press('v')
    time.sleep(0.01)
    _pynput_controller.release('v')
    _pynput_controller.release(_pynput_Key.cmd)

    time.sleep(0.05)
    return True


class KeyboardOutput:
    """Inserts text at the current cursor position via clipboard paste."""

    def __init__(self, typing_delay_ms: int = 5):
        self._use_clipboard = sys.platform in ("win32", "darwin")
        self._platform = sys.platform

    async def start(self):
        if self._platform == "win32":
            _init_win32()
        _ensure_pynput()
        mode = "clipboard-paste" if self._use_clipboard else "pynput-type"
        logger.info("KeyboardOutput initialized (mode=%s, platform=%s)", mode, self._platform)

    async def stop(self):
        pass

    async def type_text(self, text: str):
        """Insert text at the current cursor position."""
        if not text:
            return

        loop = asyncio.get_event_loop()

        if self._use_clipboard:
            paste_fn = _clipboard_paste_win32 if self._platform == "win32" else _clipboard_paste_darwin
            try:
                ok = await loop.run_in_executor(None, paste_fn, text)
                if ok:
                    logger.info("Pasted %d chars via clipboard", len(text))
                    return
                else:
                    logger.warning("Clipboard paste returned False, falling back to pynput")
            except Exception as e:
                logger.warning("Clipboard paste exception: %s, falling back to pynput", e)

        _ensure_pynput()
        await loop.run_in_executor(None, _pynput_controller.type, text)
        logger.info("Typed %d chars via pynput", len(text))

