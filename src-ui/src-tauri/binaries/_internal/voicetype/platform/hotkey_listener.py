#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Global hotkey listener for toggling voice input.
Uses pynput for cross-platform keyboard monitoring.
"""

import asyncio
import logging
from typing import Callable, Awaitable, Optional

from pynput import keyboard

logger = logging.getLogger(__name__)


class HotkeyListener:
    """Listens for a global hotkey to toggle voice recording on/off."""

    def __init__(
        self,
        hotkey: str = "<ctrl>+<shift>+v",
        on_activate: Optional[Callable[[], Awaitable[None]]] = None,
        on_deactivate: Optional[Callable[[], Awaitable[None]]] = None,
        is_active_fn: Optional[Callable[[], bool]] = None,
    ):
        self._hotkey_str = hotkey
        self._on_activate = on_activate
        self._on_deactivate = on_deactivate
        # External source of truth for recording state (e.g. engine.is_recording)
        self._is_active_fn = is_active_fn
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_active(self) -> bool:
        if self._is_active_fn:
            return self._is_active_fn()
        return False

    def _on_hotkey(self):
        """Called from pynput's listener thread when hotkey is pressed."""
        if self._loop is None:
            return

        currently_active = self.is_active

        if currently_active:
            logger.info("Voice input deactivating...")
            if self._on_deactivate:
                future = asyncio.run_coroutine_threadsafe(self._on_deactivate(), self._loop)
                future.add_done_callback(self._on_toggle_done)
        else:
            logger.info("Voice input activating...")
            if self._on_activate:
                future = asyncio.run_coroutine_threadsafe(self._on_activate(), self._loop)
                future.add_done_callback(self._on_toggle_done)

    def _on_toggle_done(self, future):
        exc = future.exception()
        if exc:
            logger.error("Hotkey toggle failed: %s", exc)

    async def start(self):
        self._loop = asyncio.get_event_loop()
        self._listener = keyboard.GlobalHotKeys({
            self._hotkey_str: self._on_hotkey,
        })
        self._listener.start()
        logger.info("HotkeyListener started: %s", self._hotkey_str)

    async def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None
        logger.info("HotkeyListener stopped")
