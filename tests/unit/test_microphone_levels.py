"""
Unit tests for Microphone level streaming and energy callback.
"""

from __future__ import annotations

import numpy as np
from unittest.mock import MagicMock, patch

from jarvis.voice.microphone import Microphone


def test_microphone_level_callback():
    mic = Microphone()

    received_levels: list[float] = []

    def on_level(lvl: float) -> None:
        received_levels.append(lvl)

    # Generate a loud audio chunk (sine wave)
    t = np.linspace(0, 1, 1280, endpoint=False)
    loud_chunk = (np.sin(2 * np.pi * 440 * t) * 20000).astype(np.int16)

    # Put mock chunk in queue
    mic._queue.put(loud_chunk)

    # Mock RawInputStream to avoid opening real hardware audio during test
    with patch("sounddevice.RawInputStream"):
        gen = mic.iter_chunks(level_callback=on_level)
        chunk = next(gen)

    assert len(chunk) == 1280
    assert len(received_levels) == 1
    assert received_levels[0] > 0.1  # Significant energy detected
