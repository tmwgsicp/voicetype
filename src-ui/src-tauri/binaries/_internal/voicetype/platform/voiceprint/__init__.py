#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Voiceprint recognition module.
声纹识别模块。
"""

from .base import (
    BaseVoiceprintService,
    VoiceprintProvider,
    VoiceprintResult,
)

from .factory import VoiceprintServiceFactory

__all__ = [
    "BaseVoiceprintService",
    "VoiceprintProvider",
    "VoiceprintResult",
    "VoiceprintServiceFactory",
]
