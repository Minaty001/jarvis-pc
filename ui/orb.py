"""
JARVIS Orb — an animated "arc-reactor" core drawn with Cairo.

The Orb is the visual heart of the UI:
  * MainWindow shows a large Orb as the HUD centerpiece.
  * FloatingOrb shows a small always-on-top Orb.

Both are the same widget at different sizes. The orb:
  - draws a glowing core whose colour reflects Jarvis's state (idle/listening/thinking/...)
  - draws 2 rotating rings of tick marks (the "arc reactor" feel)
  - pulses subtly; pulse amplitude rises when listening/speaking
"""

import cairo
import math

from gi.repository import Gtk, Gdk, GLib

from ui.theme import ORB_STATES


def _hex_to_rgba(hex_str: str, alpha: float = 1.0):
    h = hex_str.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (r, g, b, alpha)


class OrbWidget(Gtk.DrawingArea):
    def __init__(self, size: int = 220, state: str = "idle"):
        super().__init__()
        self.set_size_request(size, size)
        self._size = size
        self._state = state
        self._label = ""
        self._phase = 0.0          # rotation phase
        self._pulse = 0.0          # current pulse offset
        self._target_pulse = 0.0   # pulse target (state-driven)
        self._tick = 0
        self._animating = True
        self.set_app_paintable(True)
        self.connect("draw", self._on_draw)
        self._timer = GLib.timeout_add(33, self._tick_anim)  # ~30 fps

    # ── public API ──────────────────────────────────────────────────────
    def set_state(self, state: str) -> None:
        if state in ORB_STATES:
            self._state = state
        # pulse harder when interacting
        self._target_pulse = 0.18 if state in ("listening", "speaking", "working") else 0.05

    def set_label(self, text: str) -> None:
        self._label = text or ""

    def set_size(self, size: int) -> None:
        self._size = size
        self.set_size_request(size, size)

    def stop_animation(self) -> None:
        self._animating = False
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None

    def pause_animation(self) -> None:
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None

    def resume_animation(self) -> None:
        if self._animating and not self._timer:
            self._timer = GLib.timeout_add(33, self._tick_anim)

    # ── animation loop ──────────────────────────────────────────────────
    def _tick_anim(self) -> bool:
        if not self._animating:
            return False
        self._phase += 0.02
        # ease pulse toward target
        self._pulse += (self._target_pulse - self._pulse) * 0.1
        self._tick += 1
        self.queue_draw()
        return True

    # ── drawing ─────────────────────────────────────────────────────────
    def _on_draw(self, widget, cr):
        w = self.get_allocated_width()
        h = self.get_allocated_height()
        self._paint(cr, w, h, self._state, self._phase, self._pulse, self._label)
        return False

    # Offscreen render (used by tests / icon generation) — no GTK loop needed.
    @classmethod
    def render_to_surface(cls, size: int, state: str = "idle",
                          label: str = "", phase: float = 0.0) -> cairo.ImageSurface:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        cr = cairo.Context(surf)
        cls._paint(cr, size, size, state, phase, 0.1, label)
        return surf

    @staticmethod
    def _paint(cr, w, h, state, phase, pulse, label):
        cx, cy = w / 2.0, h / 2.0
        R = min(w, h) / 2.0 - 4.0
        core_color = ORB_STATES.get(state, ORB_STATES["idle"])

        r, g, b, _ = _hex_to_rgba(core_color)

        # outer halo
        rg = cairo.RadialGradient(cx, cy, R * 0.2, cx, cy, R)
        rg.add_color_stop_rgba(0.0, r, g, b, 0.0)
        rg.add_color_stop_rgba(0.7, r, g, b, 0.10)
        rg.add_color_stop_rgba(1.0, r, g, b, 0.0)
        cr.set_source(rg)
        cr.arc(cx, cy, R, 0, 2 * math.pi)
        cr.fill()

        # rotating ring ticks (two rings)
        OrbWidget._draw_ring(cr, cx, cy, R * 0.92, phase, 36, core_color, 0.5, 2.0, 0.18)
        OrbWidget._draw_ring(cr, cx, cy, R * 0.74, -phase * 1.3, 24, core_color, 0.7, 2.5, 0.28)

        # thin static circle (frame)
        cr.set_source_rgba(*_hex_to_rgba(core_color, 0.35))
        cr.set_line_width(1.0)
        cr.arc(cx, cy, R * 0.62, 0, 2 * math.pi)
        cr.stroke()

        # glowing core (pulsing)
        core_r = R * (0.34 + pulse * 0.25)
        cg = cairo.RadialGradient(cx, cy, core_r * 0.1, cx, cy, core_r)
        cg.add_color_stop_rgba(0.0, r, g, b, 1.0)
        cg.add_color_stop_rgba(0.6, r, g, b, 0.85)
        cg.add_color_stop_rgba(1.0, r, g, b, 0.0)
        cr.set_source(cg)
        cr.arc(cx, cy, core_r, 0, 2 * math.pi)
        cr.fill()

        # bright center dot
        cr.set_source_rgba(1, 1, 1, 0.9)
        cr.arc(cx, cy, core_r * 0.18, 0, 2 * math.pi)
        cr.fill()

        # label below orb
        if label:
            cr.set_source_rgba(*_hex_to_rgba("#e8f0ff", 0.85))
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(max(9, R * 0.12))
            tw = cr.text_extents(label).width
            cr.move_to(cx - tw / 2.0, cy + R * 0.5)
            cr.show_text(label)

    @staticmethod
    def _draw_ring(cr, cx, cy, radius, phase, n, color, alpha, lw, len_frac):
        cr.set_source_rgba(*_hex_to_rgba(color, alpha))
        cr.set_line_width(lw)
        for i in range(n):
            a0 = phase + (2 * math.pi * i / n)
            a1 = a0 + (2 * math.pi / n) * len_frac
            cr.arc(cx, cy, radius, a0, a1)
            cr.stroke()
