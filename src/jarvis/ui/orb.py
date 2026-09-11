"""JARVIS Animated Arc-Reactor Orb Widget — Pure Cairo Rendering in GTK3."""

from __future__ import annotations

import math
import logging

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


class OrbWidget(Gtk.DrawingArea if GTK_AVAILABLE else object):  # type: ignore
    """Cairo-based animated Arc-Reactor Orb widget."""

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
        self.set_app_paintable(True)
        self.connect("draw", self._on_draw)
        self.connect("destroy", self._on_destroy)
        self._timer = GLib.timeout_add(33, self._tick_anim)

    def set_state(self, state: str) -> None:
        if state in ORB_STATES:
            self._state = state
        self._target_pulse = 0.18 if state in ("listening", "speaking", "working", "thinking") else 0.05
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
        self._pulse += (self._target_pulse - self._pulse) * 0.1
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
        core_r = max(6.0, base_r * 0.42 + pulse_offset)

        hex_col = ORB_STATES.get(self._state, "#39e0a0")
        r, g, b, _ = hex_to_rgba(hex_col, 1.0)

        # 1. Background glow
        cr.save()
        glow = cairo.RadialGradient(cx, cy, core_r * 0.1, cx, cy, base_r * 1.1)
        glow.add_color_stop_rgba(0.0, r, g, b, 0.45)
        glow.add_color_stop_rgba(0.5, r, g, b, 0.15)
        glow.add_color_stop_rgba(1.0, 0.0, 0.0, 0.0, 0.0)
        cr.set_source(glow)
        cr.arc(cx, cy, base_r * 1.1, 0, 2 * math.pi)
        cr.fill()
        cr.restore()

        # 2. Outer decorative ring
        cr.save()
        cr.set_line_width(1.5)
        cr.set_source_rgba(r, g, b, 0.25)
        cr.arc(cx, cy, base_r, 0, 2 * math.pi)
        cr.stroke()
        cr.restore()

        # 3. Outer rotating tick ring (counter-clockwise)
        cr.save()
        outer_ticks = 24
        for i in range(outer_ticks):
            angle = (2 * math.pi / outer_ticks) * i - self._phase
            t_len = 7.0 if i % 3 == 0 else 4.0
            r1 = base_r - 2.0
            r2 = r1 - t_len
            x1 = cx + r1 * math.cos(angle)
            y1 = cy + r1 * math.sin(angle)
            x2 = cx + r2 * math.cos(angle)
            y2 = cy + r2 * math.sin(angle)
            cr.set_line_width(2.0 if i % 3 == 0 else 1.0)
            alpha = 0.8 if i % 3 == 0 else 0.4
            cr.set_source_rgba(r, g, b, alpha)
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()
        cr.restore()

        # 4. Middle rotating arc segment
        cr.save()
        cr.set_line_width(2.5)
        cr.set_source_rgba(r, g, b, 0.7)
        mid_r = base_r * 0.72
        cr.arc(cx, cy, mid_r, self._phase, self._phase + math.pi * 0.75)
        cr.stroke()
        cr.arc(cx, cy, mid_r, self._phase + math.pi, self._phase + math.pi * 1.75)
        cr.stroke()
        cr.restore()

        # 5. Inner rotating tick ring (clockwise)
        cr.save()
        inner_ticks = 16
        inner_r = base_r * 0.58
        for i in range(inner_ticks):
            angle = (2 * math.pi / inner_ticks) * i + (self._phase * 1.4)
            x1 = cx + inner_r * math.cos(angle)
            y1 = cy + inner_r * math.sin(angle)
            x2 = cx + (inner_r - 5.0) * math.cos(angle)
            y2 = cy + (inner_r - 5.0) * math.sin(angle)
            cr.set_line_width(1.2)
            cr.set_source_rgba(r, g, b, 0.5)
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()
        cr.restore()

        # 6. Central Arc Core
        cr.save()
        core_grad = cairo.RadialGradient(cx, cy, 0.0, cx, cy, core_r)
        core_grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.95)
        core_grad.add_color_stop_rgba(0.4, r, g, b, 0.85)
        core_grad.add_color_stop_rgba(0.85, r, g, b, 0.3)
        core_grad.add_color_stop_rgba(1.0, r, g, b, 0.0)
        cr.set_source(core_grad)
        cr.arc(cx, cy, core_r, 0, 2 * math.pi)
        cr.fill()
        cr.restore()

        # 7. Optional center label
        if self._label:
            cr.save()
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(max(10, int(base_r * 0.16)))
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.9)
            extents = cr.text_extents(self._label)
            cr.move_to(cx - extents.width / 2.0, cy + extents.height / 2.0)
            cr.show_text(self._label)
            cr.restore()

        return True
