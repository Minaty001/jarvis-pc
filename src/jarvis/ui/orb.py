"""JARVIS Animated Arc-Reactor Orb Widget — Pure Cairo Rendering with Reactive Particle Physics in GTK3."""

from __future__ import annotations

import math
import logging
import random
from typing import List

try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gtk, Gdk, GLib
    import cairo
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False
    Gtk = object  # type: ignore

from jarvis.ui.theme import ORB_STATES, hex_to_rgba

logger = logging.getLogger(__name__)


class OrbParticle:
    """Individual orbital particle around the Arc-Reactor core."""

    def __init__(self, index: int, total: int):
        self.angle = (index / total) * 2 * math.pi
        self.base_rad = random.uniform(0.55, 0.95)
        self.speed = random.uniform(0.015, 0.045) * (1 if random.random() > 0.3 else -1)
        self.size = random.uniform(1.2, 2.8)
        self.alpha = random.uniform(0.3, 0.85)

    def step(self, pulse_mult: float):
        self.angle = (self.angle + self.speed * (1.0 + pulse_mult * 3.0)) % (2 * math.pi)


class OrbWidget(Gtk.DrawingArea if GTK_AVAILABLE else object):  # type: ignore
    """Cairo-based animated Arc-Reactor Orb widget with reactive particle vortex."""

    def __init__(self, size: int = 220, state: str = "idle"):
        if not GTK_AVAILABLE:
            raise RuntimeError("GTK 3.0 or Cairo is not available.")
        super().__init__()
        self.set_size_request(size, size)
        self._size = size
        self._state = state
        self._label = ""
        self._phase = 0.0
        self._pulse = 0.0
        self._target_pulse = 0.05
        self._tick = 0
        self._animating = True

        # Initialize 32 orbital particles
        self._particles: List[OrbParticle] = [OrbParticle(i, 32) for i in range(32)]

        self.set_app_paintable(True)
        self.connect("draw", self._on_draw)
        self.connect("destroy", self._on_destroy)
        self._timer = GLib.timeout_add(33, self._tick_anim)

    def set_state(self, state: str) -> None:
        if state in ORB_STATES:
            self._state = state
        self._target_pulse = 0.22 if state in ("listening", "speaking", "working", "thinking") else 0.05
        self.queue_draw()

    def set_label(self, text: str) -> None:
        self._label = text or ""
        self.queue_draw()

    def set_size(self, size: int) -> None:
        self._size = size
        self.set_size_request(size, size)
        self.queue_draw()

    def stop_animation(self) -> None:
        self._animating = False
        if hasattr(self, "_timer") and self._timer:
            GLib.source_remove(self._timer)
            self._timer = None

    def _on_destroy(self, _widget) -> None:
        self.stop_animation()

    def _tick_anim(self) -> bool:
        if not self._animating:
            return False
        self._tick += 1
        speed = 0.06 if self._state in ("thinking", "working") else 0.02
        self._phase = (self._phase + speed) % (2 * math.pi)
        self._pulse += (self._target_pulse - self._pulse) * 0.12

        # Step orbital particles
        for p in self._particles:
            p.step(self._pulse)

        self.queue_draw()
        return True

    def _on_draw(self, _widget, cr: cairo.Context) -> bool:
        alloc = self.get_allocation()
        cx = alloc.width / 2.0
        cy = alloc.height / 2.0
        base_r = min(alloc.width, alloc.height) / 2.0 - 12.0
        if base_r < 10:
            return False

        pulse_offset = math.sin(self._tick * 0.08) * (base_r * self._pulse)
        core_r = max(6.0, base_r * 0.40 + pulse_offset)

        hex_col = ORB_STATES.get(self._state, "#39e0a0")
        r, g, b, _ = hex_to_rgba(hex_col, 1.0)

        # 1. Background radial glow
        cr.save()
        glow = cairo.RadialGradient(cx, cy, core_r * 0.1, cx, cy, base_r * 1.15)
        glow.add_color_stop_rgba(0.0, r, g, b, 0.45 + self._pulse * 0.3)
        glow.add_color_stop_rgba(0.5, r, g, b, 0.12 + self._pulse * 0.15)
        glow.add_color_stop_rgba(1.0, 0.0, 0.0, 0.0, 0.0)
        cr.set_source(glow)
        cr.arc(cx, cy, base_r * 1.15, 0, 2 * math.pi)
        cr.fill()
        cr.restore()

        # 2. Orbital Particle Vortex
        cr.save()
        for p in self._particles:
            p_rad = base_r * (p.base_rad + self._pulse * 0.18)
            px = cx + math.cos(p.angle) * p_rad
            py = cy + math.sin(p.angle) * p_rad
            p_size = p.size * (1.0 + self._pulse * 0.5)

            cr.set_source_rgba(r, g, b, p.alpha * (0.6 + self._pulse * 0.4))
            cr.arc(px, py, p_size, 0, 2 * math.pi)
            cr.fill()
        cr.restore()

        # 3. Outer Segmented Ring
        cr.save()
        cr.set_line_width(2.0)
        cr.set_source_rgba(r, g, b, 0.4)
        num_segments = 12
        seg_len = (2 * math.pi) / num_segments
        for i in range(num_segments):
            start_a = i * seg_len + self._phase
            end_a = start_a + seg_len * 0.65
            cr.arc(cx, cy, base_r * 0.95, start_a, end_a)
            cr.stroke()
        cr.restore()

        # 4. Middle Counter-Rotating Dash Ring
        cr.save()
        cr.set_line_width(1.5)
        cr.set_source_rgba(r, g, b, 0.6)
        cr.set_dash([4.0, 6.0], -self._phase * 15.0)
        cr.arc(cx, cy, base_r * 0.72, 0, 2 * math.pi)
        cr.stroke()
        cr.restore()

        # 5. Core Arc-Reactor Ring with 6 Power Nodes
        cr.save()
        cr.set_line_width(2.5)
        cr.set_source_rgba(r, g, b, 0.85)
        cr.arc(cx, cy, core_r, 0, 2 * math.pi)
        cr.stroke()

        # Nodes
        for i in range(6):
            ang = (i / 6.0) * 2 * math.pi + self._phase * 0.5
            nx = cx + math.cos(ang) * core_r
            ny = cy + math.sin(ang) * core_r
            cr.set_source_rgba(r, g, b, 0.95)
            cr.arc(nx, ny, 3.0 + self._pulse * 2.0, 0, 2 * math.pi)
            cr.fill()
        cr.restore()

        # 6. Center Inner Core Bloom
        cr.save()
        inner_glow = cairo.RadialGradient(cx, cy, 0, cx, cy, core_r * 0.6)
        inner_glow.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.9)
        inner_glow.add_color_stop_rgba(0.4, r, g, b, 0.8)
        inner_glow.add_color_stop_rgba(1.0, r, g, b, 0.0)
        cr.set_source(inner_glow)
        cr.arc(cx, cy, core_r * 0.6, 0, 2 * math.pi)
        cr.fill()
        cr.restore()

        # 7. Center Status Label
        if self._label:
            cr.save()
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(max(10.0, base_r * 0.16))
            extents = cr.text_extents(self._label)
            cr.move_to(cx - extents.width / 2.0 - extents.x_bearing, cy - extents.height / 2.0 - extents.y_bearing)
            cr.show_text(self._label)
            cr.restore()

        return True
