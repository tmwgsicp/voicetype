#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Active window detection - cross-platform.
Polls the OS for the currently focused window and exposes app name + title.
"""

import asyncio
import logging
import platform
import dataclasses
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class WindowInfo:
    app_name: str = ""
    window_title: str = ""
    process_path: str = ""
    pid: int = 0

    def __eq__(self, other):
        if not isinstance(other, WindowInfo):
            return False
        return self.pid == other.pid and self.window_title == other.window_title


def _get_window_info_win32() -> WindowInfo:
    """Windows: use win32gui + win32process."""
    import win32gui
    import win32process
    import psutil

    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return WindowInfo()

    title = win32gui.GetWindowText(hwnd)
    _, pid = win32process.GetWindowThreadProcessId(hwnd)

    try:
        proc = psutil.Process(pid)
        app_name = proc.name()
        process_path = proc.exe()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        app_name = ""
        process_path = ""

    return WindowInfo(
        app_name=app_name,
        window_title=title,
        process_path=process_path,
        pid=pid,
    )


def _get_window_info_darwin() -> WindowInfo:
    """macOS: use NSWorkspace via pyobjc."""
    from AppKit import NSWorkspace

    workspace = NSWorkspace.sharedWorkspace()
    active_app = workspace.frontmostApplication()
    if not active_app:
        return WindowInfo()

    return WindowInfo(
        app_name=active_app.localizedName() or "",
        window_title=active_app.localizedName() or "",
        process_path=active_app.bundleURL().path() if active_app.bundleURL() else "",
        pid=active_app.processIdentifier(),
    )


def _get_window_info_linux() -> WindowInfo:
    """Linux: use X11 via python-xlib."""
    try:
        from Xlib import display as xdisplay, X
        import psutil
        
        disp = xdisplay.Display()
        window = disp.get_input_focus().focus
        
        # 获取窗口属性
        wm_class = window.get_wm_class()
        wm_name = window.get_wm_name()
        net_wm_pid = window.get_full_property(disp.intern_atom('_NET_WM_PID'), X.AnyPropertyType)
        
        app_name = wm_class[1] if wm_class else ""
        window_title = wm_name or ""
        pid = net_wm_pid.value[0] if net_wm_pid else 0
        
        process_path = ""
        if pid:
            try:
                proc = psutil.Process(pid)
                process_path = proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return WindowInfo(
            app_name=app_name,
            window_title=window_title,
            process_path=process_path,
            pid=pid,
        )
    except Exception as e:
        logger.warning("Linux window detection failed: %s", e)
        return WindowInfo()


def _get_window_info() -> WindowInfo:
    system = platform.system()
    if system == "Windows":
        return _get_window_info_win32()
    elif system == "Darwin":
        return _get_window_info_darwin()
    elif system == "Linux":
        return _get_window_info_linux()
    else:
        logger.warning("Unsupported platform for window detection: %s", system)
        return WindowInfo()


class WindowWatcher:
    """Polls the active window at a fixed interval, fires callback on change."""

    def __init__(self, poll_interval_ms: int = 200):
        self._poll_interval = poll_interval_ms / 1000.0
        self._current: WindowInfo = WindowInfo()
        self._on_change: Optional[Callable[[WindowInfo], Awaitable[None]]] = None
        self._task: Optional[asyncio.Task] = None

    @property
    def current(self) -> WindowInfo:
        return self._current

    def on_change(self, callback: Callable[[WindowInfo], Awaitable[None]]):
        self._on_change = callback

    async def start(self):
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("WindowWatcher started (interval=%dms)", int(self._poll_interval * 1000))

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("WindowWatcher stopped")

    async def _poll_loop(self):
        loop = asyncio.get_event_loop()
        while True:
            try:
                info = await loop.run_in_executor(None, _get_window_info)
                if info != self._current:
                    self._current = info
                    logger.debug("Window changed: %s - %s", info.app_name, info.window_title)
                    if self._on_change:
                        await self._on_change(info)
            except Exception as e:
                logger.error("WindowWatcher poll error: %s", e)
            await asyncio.sleep(self._poll_interval)
