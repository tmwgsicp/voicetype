#!/usr/bin/env python3
# Copyright (C) 2026 VoiceForge Contributors
# Licensed under AGPL-3.0

"""
Extension lifecycle management with state machine.
Extension 生命周期管理（状态机）。
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ExtensionState(Enum):
    """Extension 生命周期状态"""
    CREATED = "created"
    STARTING = "starting"
    READY = "ready"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class LifecycleManager:
    """生命周期管理器"""
    
    VALID_TRANSITIONS = {
        ExtensionState.CREATED: [ExtensionState.STARTING],
        ExtensionState.STARTING: [ExtensionState.READY, ExtensionState.ERROR],
        ExtensionState.READY: [ExtensionState.RUNNING, ExtensionState.STOPPING],
        ExtensionState.RUNNING: [ExtensionState.PAUSING, ExtensionState.STOPPING],
        ExtensionState.PAUSING: [ExtensionState.PAUSED, ExtensionState.ERROR],
        ExtensionState.PAUSED: [ExtensionState.RUNNING, ExtensionState.STOPPING],
        ExtensionState.STOPPING: [ExtensionState.STOPPED, ExtensionState.ERROR],
        ExtensionState.STOPPED: [],
        ExtensionState.ERROR: [ExtensionState.STOPPING],
    }
    
    def __init__(self, extension_name: str):
        self.extension_name = extension_name
        self.state = ExtensionState.CREATED
        self._state_listeners: list[Callable] = []
        self._error: Optional[Exception] = None
    
    def on_state_change(self, listener: Callable):
        """注册状态变化监听器"""
        self._state_listeners.append(listener)
    
    async def _notify_state_change(self, old_state: ExtensionState, new_state: ExtensionState):
        """通知状态变化"""
        logger.info(f"[{self.extension_name}] 状态变化: {old_state.value} -> {new_state.value}")
        for listener in self._state_listeners:
            try:
                result = listener(old_state, new_state)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"[{self.extension_name}] 状态监听器执行失败: {e}")
    
    async def transition_to(self, new_state: ExtensionState):
        """状态转换"""
        old_state = self.state
        
        if not self._is_valid_transition(old_state, new_state):
            raise ValueError(
                f"[{self.extension_name}] 非法的状态转换: {old_state.value} -> {new_state.value}"
            )
        
        self.state = new_state
        await self._notify_state_change(old_state, new_state)
    
    def _is_valid_transition(self, from_state: ExtensionState, to_state: ExtensionState) -> bool:
        """验证状态转换是否合法"""
        return to_state in self.VALID_TRANSITIONS.get(from_state, [])
    
    def is_ready(self) -> bool:
        """是否就绪"""
        return self.state in [ExtensionState.READY, ExtensionState.RUNNING]
    
    def is_running(self) -> bool:
        """是否运行中"""
        return self.state == ExtensionState.RUNNING
    
    def is_stopped(self) -> bool:
        """是否已停止"""
        return self.state == ExtensionState.STOPPED
    
    def is_error(self) -> bool:
        """是否错误状态"""
        return self.state == ExtensionState.ERROR
    
    def set_error(self, error: Exception):
        """设置错误状态"""
        self._error = error
        self.state = ExtensionState.ERROR
        logger.error(f"[{self.extension_name}] 进入错误状态: {error}")
    
    def get_error(self) -> Optional[Exception]:
        """获取错误信息"""
        return self._error
