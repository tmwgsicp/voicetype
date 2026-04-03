#!/usr/bin/env python3
# Copyright (C) 2026 VoiceForge Contributors
# Licensed under AGPL-3.0

"""
Message priority definitions.
消息优先级定义。
"""

from enum import Enum


class MessagePriority(Enum):
    """消息优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3
