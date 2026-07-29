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

    u32.GetClipboardData.argtypes = [w.UINT]
    u32.GetClipboardData.restype = ctypes.c_void_p

    _win32_ready = True


def _win32_set_clipboard_text(text: str) -> bool:
    """打开剪贴板并写入文本（供粘贴和恢复复用）。"""
    import ctypes, time
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.03)
    else:
        return False
    try:
        user32.EmptyClipboard()
        data = text.encode("utf-16-le") + b"\x00\x00"
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h_mem:
            return False
        ptr = kernel32.GlobalLock(h_mem)
        if not ptr:
            kernel32.GlobalFree(h_mem)
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(h_mem)
        if not user32.SetClipboardData(CF_UNICODETEXT, h_mem):
            kernel32.GlobalFree(h_mem)
            return False
        return True
    finally:
        user32.CloseClipboard()


def _win32_get_clipboard_text():
    """读取剪贴板文本（无则返回 None）。"""
    import ctypes, time
    _init_win32()
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    CF_UNICODETEXT = 13
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.02)
    else:
        return None
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        ptr = kernel32.GlobalLock(h)
        if not ptr:
            return None
        text = ctypes.wstring_at(ptr)
        kernel32.GlobalUnlock(h)
        return text
    finally:
        user32.CloseClipboard()


def _win32_get_selection() -> str:
    """模拟 Ctrl+C 复制当前选中的文本，读出后恢复原剪贴板。返回选中文本（无则空）。"""
    import ctypes, time
    _init_win32()
    user32 = ctypes.windll.user32
    VK_CONTROL, VK_C, KEYEVENTF_KEYUP = 0x11, 0x43, 0x0002
    prev = _win32_get_clipboard_text()
    _win32_set_clipboard_text("\x00__vt_sentinel__")  # 便于判断是否真复制到内容
    time.sleep(0.03)
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.01)
    user32.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.12)
    sel = _win32_get_clipboard_text() or ""
    if prev is not None:
        _win32_set_clipboard_text(prev)
    if sel == "\x00__vt_sentinel__":  # Ctrl+C 没复制到东西（没选中）
        sel = ""
    return sel


def _win32_get_cursor_pos():
    """返回鼠标光标屏幕坐标 (x, y)。用于在光标处弹出编辑菜单。"""
    import ctypes

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return (int(pt.x), int(pt.y))


def _win32_get_foreground_window():
    """返回当前前台窗口句柄（int）。弹菜单前记住目标程序，套用后好切回去。"""
    import ctypes
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    hwnd = user32.GetForegroundWindow()
    return int(hwnd) if hwnd else 0


def _win32_set_foreground_window(hwnd: int) -> bool:
    """把焦点切回指定窗口（编辑菜单窗抢走焦点后，套用前切回目标程序）。

    Windows 对 SetForegroundWindow 有前台锁限制：非前台进程直接调用常失败。
    用 AttachThreadInput 把本线程临时挂到前台线程+目标线程，绕过限制——这是标准做法。
    """
    if not hwnd:
        return False
    import ctypes
    from ctypes import wintypes as w
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.GetForegroundWindow.restype = ctypes.c_void_p
    user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.GetWindowThreadProcessId.restype = w.DWORD
    user32.AttachThreadInput.argtypes = [w.DWORD, w.DWORD, w.BOOL]
    user32.AttachThreadInput.restype = w.BOOL
    user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    user32.SetForegroundWindow.restype = w.BOOL
    user32.BringWindowToTop.argtypes = [ctypes.c_void_p]
    user32.IsIconic.argtypes = [ctypes.c_void_p]
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]

    SW_RESTORE = 9
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    fg = user32.GetForegroundWindow()
    if fg and int(fg) == int(hwnd):
        return True

    cur_thread = kernel32.GetCurrentThreadId()
    fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)

    attached_fg = attached_tgt = False
    try:
        if fg_thread and fg_thread != cur_thread:
            attached_fg = bool(user32.AttachThreadInput(cur_thread, fg_thread, True))
        if target_thread and target_thread != cur_thread and target_thread != fg_thread:
            attached_tgt = bool(user32.AttachThreadInput(cur_thread, target_thread, True))
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        new_fg = user32.GetForegroundWindow()
        return bool(new_fg and int(new_fg) == int(hwnd))
    finally:
        if attached_fg:
            user32.AttachThreadInput(cur_thread, fg_thread, False)
        if attached_tgt:
            user32.AttachThreadInput(cur_thread, target_thread, False)


def _darwin_get_cursor_pos():
    """macOS: 返回鼠标光标坐标 (x, y)。"""
    try:
        from AppKit import NSEvent
        loc = NSEvent.mouseLocation()
        # NSEvent 原点在左下，屏幕坐标原点在左上，这里用主屏高度翻转
        from AppKit import NSScreen
        screen_h = NSScreen.mainScreen().frame().size.height
        return (int(loc.x), int(screen_h - loc.y))
    except Exception:
        return (0, 0)


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

    prev_text = None
    try:
        # 先保存用户原有的剪贴板文本，粘贴完成后恢复，避免一次听写清空用户剪贴板
        try:
            h_prev = user32.GetClipboardData(CF_UNICODETEXT)
            if h_prev:
                ptr_prev = kernel32.GlobalLock(h_prev)
                if ptr_prev:
                    prev_text = ctypes.wstring_at(ptr_prev)
                    kernel32.GlobalUnlock(h_prev)
        except Exception:
            prev_text = None

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

    # 恢复用户原来的剪贴板内容（不要因为一次听写就清空用户的剪贴板）
    if prev_text:
        time.sleep(0.05)
        try:
            _win32_set_clipboard_text(prev_text)
        except Exception:
            pass

    return True


def _darwin_get_selection() -> str:
    """macOS: 模拟 Cmd+C 复制选中文本，读出后恢复原剪贴板。"""
    import subprocess, time
    prev = None
    try:
        prev = subprocess.run(["pbpaste"], capture_output=True, timeout=2).stdout
    except Exception:
        prev = None
    subprocess.run(["pbcopy"], input=b"", timeout=2)  # 清空以便判断
    time.sleep(0.03)
    _ensure_pynput()
    _pynput_controller.press(_pynput_Key.cmd)
    _pynput_controller.press('c')
    time.sleep(0.02)
    _pynput_controller.release('c')
    _pynput_controller.release(_pynput_Key.cmd)
    time.sleep(0.12)
    sel = ""
    try:
        sel = subprocess.run(["pbpaste"], capture_output=True, timeout=2).stdout.decode("utf-8", "replace")
    except Exception:
        sel = ""
    if prev is not None:
        try:
            subprocess.run(["pbcopy"], input=prev, timeout=2)
        except Exception:
            pass
    return sel


def _clipboard_paste_darwin(text: str) -> bool:
    """macOS: write text to clipboard via pbcopy, then simulate Cmd+V."""
    import subprocess
    import time

    # 先保存用户原有剪贴板，粘贴后恢复，避免清空用户剪贴板
    prev = None
    try:
        prev = subprocess.run(["pbpaste"], capture_output=True, timeout=2).stdout
    except Exception:
        prev = None

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

    # 恢复用户原来的剪贴板内容
    if prev is not None:
        try:
            subprocess.run(["pbcopy"], input=prev, timeout=2)
        except Exception:
            pass

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

    async def get_selection(self) -> str:
        """复制并返回当前选中的文本（用于语音编辑）。在线程池执行，不阻塞事件循环。"""
        loop = asyncio.get_event_loop()
        try:
            if self._platform == "win32":
                return await loop.run_in_executor(None, _win32_get_selection)
            elif self._platform == "darwin":
                return await loop.run_in_executor(None, _darwin_get_selection)
        except Exception as e:
            logger.warning("get_selection failed: %s", e)
        return ""

    async def get_cursor_pos(self) -> tuple[int, int]:
        """当前鼠标光标屏幕坐标（用于在光标处弹编辑菜单）。失败返回 (0, 0)。"""
        loop = asyncio.get_event_loop()
        try:
            if self._platform == "win32":
                return await loop.run_in_executor(None, _win32_get_cursor_pos)
            elif self._platform == "darwin":
                return await loop.run_in_executor(None, _darwin_get_cursor_pos)
        except Exception as e:
            logger.warning("get_cursor_pos failed: %s", e)
        return (0, 0)

    async def get_foreground_window(self) -> int:
        """当前前台窗口句柄（弹菜单前记住目标程序）。非 Windows 或失败返回 0。"""
        if self._platform != "win32":
            return 0
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, _win32_get_foreground_window)
        except Exception as e:
            logger.warning("get_foreground_window failed: %s", e)
        return 0

    async def focus_window(self, hwnd: int) -> bool:
        """把焦点切回指定窗口（套用改写前，从菜单窗切回目标程序）。"""
        if self._platform != "win32" or not hwnd:
            return False
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, _win32_set_foreground_window, hwnd)
        except Exception as e:
            logger.warning("focus_window failed: %s", e)
        return False

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

