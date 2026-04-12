#!/usr/bin/env python3
# Copyright (C) 2026 VoiceForge Contributors
# Licensed under AGPL-3.0

"""
Extension base class and port definitions.
Extension 基类和端口定义。

All functional modules (ASR) inherit from Extension.
Each Extension declares input/output ports, and the framework handles connections and routing.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Callable, Generic, TypeVar, Union

from .config import ExtensionConfig
from .lifecycle import ExtensionState, LifecycleManager
from .message import MessagePriority
from .error_handler import ErrorHandler, RetryPolicy

logger = logging.getLogger(__name__)

ConfigT = TypeVar('ConfigT', bound=ExtensionConfig)


class PortType(Enum):
    """端口数据类型"""
    AUDIO_FRAME = "audio_frame"
    TEXT = "text"
    TEXT_STREAM = "text_stream"
    COMMAND = "command"
    ANY = "any"


@dataclass
class Port:
    """扩展的输入/输出端口"""
    name: str
    port_type: PortType
    description: str = ""
    required: bool = True


@dataclass
class ExtensionMeta:
    """扩展的元数据"""
    name: str
    description: str = ""
    version: str = "0.1.0"
    category: str = "general"


class Extension(ABC, Generic[ConfigT]):
    """可插拔功能模块的基类（增强版，支持泛型配置）

    子类需要实现：
      - metadata: 扩展元数据
      - input_ports / output_ports: 端口声明
      - config_class: 配置类（类属性）
      - _do_start(): 初始化资源（WebSocket 连接等）
      - on_data(): 接收并处理数据
      - _do_stop(): 清理资源
    """

    metadata: ExtensionMeta = ExtensionMeta(name="base")
    input_ports: list[Port] = []
    output_ports: list[Port] = []
    
    config_class: type[ConfigT] = ExtensionConfig

    def __init__(self, config: Union[ConfigT, dict[str, Any], None] = None):
        if isinstance(config, dict):
            self.config: ConfigT = self.config_class(**config)
        elif isinstance(config, ExtensionConfig):
            self.config: ConfigT = config
        else:
            self.config: ConfigT = self.config_class(name=self.metadata.name)
        
        self.lifecycle = LifecycleManager(self.config.name)
        self.error_handler = ErrorHandler(
            retry_policy=RetryPolicy(max_attempts=self.config.retry_count + 1)
        )
        
        self._downstream: dict[str, list[Callable]] = {}
        self._running = False
        self._tasks: list[asyncio.Task] = []

    def connect(self, output_port: str, callback: Callable):
        """注册下游回调（由 Graph 在构建时调用）"""
        self._downstream.setdefault(output_port, []).append(callback)

    async def send(self, port_name: str, data: Any, priority: MessagePriority = MessagePriority.NORMAL):
        """向指定输出端口发送数据"""
        if not self.lifecycle.is_ready():
            logger.warning(f"[{self.config.name}] Extension 未就绪，无法发送数据")
            return
        
        for cb in self._downstream.get(port_name, []):
            try:
                result = cb(data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"[{self.config.name}] 发送数据到端口 {port_name} 失败: {e}")

    async def send_stream(self, port_name: str, stream: AsyncIterator[Any]):
        """向指定端口发送流式数据"""
        if not self.lifecycle.is_ready():
            logger.warning(f"[{self.config.name}] Extension 未就绪，无法发送数据")
            return
        
        for cb in self._downstream.get(port_name, []):
            try:
                result = cb(stream)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"[{self.config.name}] 发送流到端口 {port_name} 失败: {e}")

    async def on_start(self):
        """启动 Extension（带状态管理）"""
        await self.lifecycle.transition_to(ExtensionState.STARTING)
        
        try:
            await self._do_start()
            await self.lifecycle.transition_to(ExtensionState.READY)
            await self.lifecycle.transition_to(ExtensionState.RUNNING)
            self._running = True
        except Exception as e:
            self.lifecycle.set_error(e)
            raise

    @abstractmethod
    async def _do_start(self):
        """子类实现具体启动逻辑"""
        pass

    @abstractmethod
    async def on_data(self, port: str, data: Any):
        """接收输入数据"""
        pass

    async def on_stop(self):
        """停止 Extension（带状态管理）"""
        if self.lifecycle.is_stopped():
            return
        
        await self.lifecycle.transition_to(ExtensionState.STOPPING)
        
        try:
            self._running = False
            
            for t in self._tasks:
                t.cancel()
            
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
            
            await self._do_stop()
            
            await self.lifecycle.transition_to(ExtensionState.STOPPED)
        except Exception as e:
            self.lifecycle.set_error(e)
            logger.error(f"[{self.config.name}] 停止时发生错误: {e}")

    async def _do_stop(self):
        """子类实现具体停止逻辑（可选）"""
        pass

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "name": self.config.name,
            "state": self.lifecycle.state.value,
            "error_handler": self.error_handler.get_stats(),
        }

    def __repr__(self):
        return f"<Extension:{self.config.name} state={self.lifecycle.state.value}>"
