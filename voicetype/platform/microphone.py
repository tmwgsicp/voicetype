#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Microphone audio capture using sounddevice.
Captures PCM 16kHz 16-bit mono audio and delivers chunks via async callback.
"""

import asyncio
import logging
from typing import Optional, Callable, Awaitable

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
CHUNK_SAMPLES = 1600


class Microphone:
    """Captures audio from the default microphone, delivers PCM chunks."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        chunk_samples: int = CHUNK_SAMPLES,
        device: Optional[int] = None,
    ):
        self._sample_rate = sample_rate
        self._chunk_samples = chunk_samples
        self._device = device
        self._stream: Optional[sd.InputStream] = None
        self._on_audio: Optional[Callable[[bytes], Awaitable[None]]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def on_audio(self, callback: Callable[[bytes], Awaitable[None]]):
        """Register async callback for audio chunks (PCM int16 bytes)."""
        self._on_audio = callback

    def start(self, loop: asyncio.AbstractEventLoop):
        """Start capturing audio. Must be called from the asyncio event loop thread."""
        if self._stream is not None:
            return

        self._loop = loop

        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=self._chunk_samples,
            device=self._device,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info(
            "Microphone started (rate=%dHz, chunk=%d samples, device=%s)",
            self._sample_rate, self._chunk_samples, self._device or "default",
        )

    def stop(self):
        """Stop capturing audio."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            logger.info("Microphone stopped")

    @property
    def is_active(self) -> bool:
        return self._stream is not None and self._stream.active

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """sounddevice callback -- runs in a separate audio thread."""
        if status:
            logger.warning("Audio status: %s", status)

        if self._on_audio and self._loop:
            pcm_bytes = indata.tobytes()
            self._loop.call_soon_threadsafe(
                asyncio.ensure_future,
                self._on_audio(pcm_bytes),
            )
