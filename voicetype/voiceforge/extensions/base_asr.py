#!/usr/bin/env python3
# Copyright (C) 2026 VoiceForge Contributors
# Licensed under AGPL-3.0

"""
Abstract ASR Extension interface.
ASR 扩展抽象接口。
"""

from abc import ABC, abstractmethod
from voicetype.voiceforge.core.extension import Extension


class BaseASRExtension(Extension, ABC):
    """
    Abstract base class for ASR extensions.
    ASR 扩展抽象基类。
    """
    
    @abstractmethod
    async def establish_connection(self):
        """Establish ASR connection."""
        pass
    
    @abstractmethod
    async def send_audio(self, audio_data: bytes):
        """Send audio data to ASR service."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Close ASR connection and clean up resources."""
        pass
