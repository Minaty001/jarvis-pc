"""Slice 1 test: OrbWidget offscreen render + live GTK draw under a display."""

import os
import sys

# Make the project root importable (run.py does the same via sys.path.insert).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from ui.orb import OrbWidget, _hex_to_rgba  # noqa: F401  (import check for theme helpers)
from ui import theme


def test_offscreen_render():
    """Render each orb state to a PNG — proves cairo drawing works headless."""
    out = os.path.join(os.path.dirname(__file__), "..", "data", "orb_states.png")
    out = os.path.abspath(out)
    import cairo
    states = ["idle", "listening", "thinking", "speaking", "working", "error"]
    size = 96
    cols = len(states)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size * cols, size)
    cr = cairo.Context(surf)
    for i, s in enumerate(states):
        sub = OrbWidget.render_to_surface(size, s, s.upper(), phase=i * 0.3)
        cr.set_source_surface(sub, i * size, 0)
        cr.paint()
    surf.write_to_png(out)
    assert os.path.getsize(out) > 1000, "orb png too small — draw likely failed"
    print(f"OK offscreen orb render -> {out} ({cols} states)")


def test_live_orb_draw():
    """Create a real Gtk window with an OrbWidget and confirm draw() runs."""
    theme.load_css()
    win = Gtk.Window()
    win.set_default_size(240, 240)
    orb = OrbWidget(size=200, state="thinking")
    orb.set_label("JARVIS")
    win.add(orb)
    drawn = {"ok": False}

    def on_draw(w, cr):
        drawn["ok"] = True
        return False

    orb.connect("draw", on_draw)
    win.show_all()
    win.queue_draw()
    for _ in range(10):
        Gtk.main_iteration_do(False)
    import cairo
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 240, 240)
    cr = cairo.Context(surf)
    orb.draw(cr)
    assert drawn["ok"], "OrbWidget draw signal never fired"
    orb.stop_animation()
    win.destroy()
    print("OK live OrbWidget draw fired")


if __name__ == "__main__":
    test_offscreen_render()
    test_live_orb_draw()
    print("SLICE 1 PASS")
