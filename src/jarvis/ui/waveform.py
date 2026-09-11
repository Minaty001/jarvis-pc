"""
JARVIS Real-Time Audio Waveform & Spectrum Equalizer Widget — Pure Cairo Rendering in GTK3.
"""

from __future__ import annotations

import math
import logging
from typing import List, Optional

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, GLib
    import cairo
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False
    Gtk = object  # type: ignore

from jarvis.ui.theme import ORB_STATES, hex_to_rgba

logger = logging.getLogger(__name__)


class WaveformWidget(Gtk.DrawingArea if GTK_AVAILABLE else object):  # type: ignore
    """Real-time Cairo animated audio waveform and multi-band frequency visualizer."""

    def __init__(self, width: int = 260, height: int = 60, state: str = "idle"):
        if not GTK_AVAILABLE:
            raise RuntimeError("GTK 3.0 or Cairo is not available.")
        super().__init__()
        self.set_size_request(width, height)
        self._width = width
        self._height = height
        self._state = state

        self._phase = 0.0
        self._level = 0.05
        self._target_level = 0.05
        self._tick = 0
        self._animating = True

        # 16-band spectrum bar levels & peak hold
        self._num_bars = 16
        self._bars: List[float] = [0.05] * self._num_bars
        self._peaks: List[float] = [0.05] * self._num_bars

        self.set_app_paintable(True)
        self.connect("draw", self._on_draw)
        self.connect("destroy", self._on_destroy)
        self._timer = GLib.timeout_add(33, self._tick_anim)

    def set_state(self, state: str) -> None:
        """Update active visualizer state (idle, listening, thinking, speaking, working, error)."""
        if state in ORB_STATES:
            self._state = state
        self.queue_draw()

    def feed_level(self, amplitude: float) -> None:
        """Feed normalized audio energy amplitude (0.0 to 1.0)."""
        clamped = max(0.0, min(1.0, float(amplitude)))
        self._target_level = clamped
        self.queue_draw()

    def stop_animation(self) -> None:
        """Stop animation timer on destruction."""
        self._animating = False
        if hasattr(self, "_timer") and self._timer:
            GLib.source_remove(self._timer)
            self._timer = None

    def _on_destroy(self, _widget: object) -> None:
        self.stop_animation()

    def _tick_anim(self) -> bool:
        if not self._animating:
            return False
        self._tick += 1

        # Smooth audio energy with fast attack and graceful exponential decay
        if self._target_level > self._level:
            self._level += (self._target_level - self._level) * 0.45
        else:
            self._level += (self._target_level - self._level) * 0.12

        # In speaking mode, oscillate target level to mimic speech rhythm
        if self._state == "speaking":
            synthetic_energy = 0.35 + 0.30 * math.sin(self._tick * 0.22) * math.cos(self._tick * 0.15)
            self._level += (synthetic_energy - self._level) * 0.25
        elif self._state == "thinking":
            synthetic_energy = 0.20 + 0.15 * math.sin(self._tick * 0.18)
            self._level += (synthetic_energy - self._level) * 0.20

        # Phase progression speed
        speed = 0.08 if self._state in ("speaking", "listening") else 0.03
        self._phase = (self._phase + speed) % (2 * math.pi)

        # Decay target energy slowly towards ambient baseline
        baseline = 0.06 if self._state == "idle" else 0.12
        self._target_level += (baseline - self._target_level) * 0.08

        # Animate multi-band spectrum bars
        for i in range(self._num_bars):
            harmonic = math.sin(self._phase * 1.5 + i * 0.45) * 0.3 + 0.7
            target_bar = min(1.0, max(0.04, self._level * harmonic * (1.1 - abs(i - 7.5) / 10.0)))
            self._bars[i] += (target_bar - self._bars[i]) * 0.35

            # Peak hold
            if self._bars[i] >= self._peaks[i]:
                self._peaks[i] = self._bars[i]
            else:
                self._peaks[i] = max(0.04, self._peaks[i] - 0.015)

        self.queue_draw()
        return True

    def _on_draw(self, _widget: object, cr: cairo.Context) -> bool:
        alloc = self.get_allocation()
        w = alloc.width
        h = alloc.height
        if w < 10 or h < 10:
            return False

        cy = h / 2.0
        hex_col = ORB_STATES.get(self._state, "#39e0a0")
        r, g, b, _ = hex_to_rgba(hex_col, 1.0)

        # 1. Background glow bar
        cr.save()
        bg_glow = cairo.LinearGradient(0, cy - h / 3.0, 0, cy + h / 3.0)
        bg_glow.add_color_stop_rgba(0.0, r, g, b, 0.0)
        bg_glow.add_color_stop_rgba(0.5, r, g, b, 0.08 + self._level * 0.15)
        bg_glow.add_color_stop_rgba(1.0, r, g, b, 0.0)
        cr.rectangle(0, 0, w, h)
        cr.set_source(bg_glow)
        cr.fill()
        cr.restore()

        # 2. Render spectrum equalizer bars in background
        cr.save()
        bar_w = (w - (self._num_bars * 3)) / self._num_bars
        max_bar_h = h * 0.75
        for i in range(self._num_bars):
            bx = i * (bar_w + 3) + 2
            bh = self._bars[i] * max_bar_h
            by = cy - bh / 2.0

            # Bar
            cr.set_source_rgba(r, g, b, 0.22 + self._bars[i] * 0.35)
            cr.rectangle(bx, by, bar_w, bh)
            cr.fill()

            # Peak Cap
            py = cy - (self._peaks[i] * max_bar_h) / 2.0
            cr.set_source_rgba(r, g, b, 0.75)
            cr.rectangle(bx, py - 1.5, bar_w, 2.0)
            cr.fill()
        cr.restore()

        # 3. Render 3 layered harmonic sine waves with fading alpha
        layers = [
            {"freq": 1.8, "amp_mult": 0.5, "phase_shift": 0.0, "alpha": 0.35, "width": 1.2},
            {"freq": 2.6, "amp_mult": 0.75, "phase_shift": 1.2, "alpha": 0.60, "width": 1.8},
            {"freq": 3.4, "amp_mult": 1.0, "phase_shift": 2.4, "alpha": 0.95, "width": 2.4},
        ]

        max_amp = (h / 2.0 - 4.0) * (0.15 + self._level * 0.85)

        for layer in layers:
            cr.save()
            cr.set_line_width(layer["width"])
            cr.set_source_rgba(r, g, b, layer["alpha"])

            cr.move_to(0, cy)
            steps = int(w / 4)
            for i in range(steps + 1):
                x = (i / steps) * w
                norm_x = x / w
                envelope = math.sin(norm_x * math.pi)
                wave_val = math.sin(norm_x * layer["freq"] * 2 * math.pi + self._phase + layer["phase_shift"])
                y = cy + wave_val * max_amp * layer["amp_mult"] * envelope
                cr.line_to(x, y)

            cr.stroke()
            cr.restore()

        return True
