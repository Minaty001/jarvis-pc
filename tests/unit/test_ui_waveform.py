"""
Unit tests for Cairo WaveformWidget.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from jarvis.ui.waveform import WaveformWidget


def test_waveform_widget_lifecycle():
    widget = WaveformWidget(width=200, height=40, state="idle")
    assert widget._width == 200
    assert widget._height == 40
    assert widget._state == "idle"

    # Test state changes
    widget.set_state("listening")
    assert widget._state == "listening"

    widget.set_state("speaking")
    assert widget._state == "speaking"

    widget.set_state("thinking")
    assert widget._state == "thinking"

    # Test feed level and clamping
    widget.feed_level(0.75)
    assert widget._target_level == 0.75

    widget.feed_level(1.5)
    assert widget._target_level == 1.0

    widget.feed_level(-0.2)
    assert widget._target_level == 0.0

    # Test animation tick
    running = widget._tick_anim()
    assert running is True
    assert widget._tick > 0

    # Test stop animation
    widget.stop_animation()
    assert widget._animating is False
    assert widget._tick_anim() is False
