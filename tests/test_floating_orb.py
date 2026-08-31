"""Slice 2 test: FloatingOrb window — always-on-top, draggable, click toggles main."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gi.repository import Gtk, Gdk

from ui import theme
from ui.floating_orb import FloatingOrb
from ui.orb import OrbWidget


def test_floating_orb():
    theme.load_css()
    toggled = {"n": 0, "quit": False}

    def on_toggle():
        toggled["n"] += 1

    def on_quit():
        toggled["quit"] = True

    orb = FloatingOrb(size=96, on_toggle=on_toggle, on_quit=on_quit)
    orb.set_state("listening")
    orb.set_label("")
    orb.show_all()

    # process initial events (placement, draw)
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)

    # window must be realized & visible
    assert orb.get_visible(), "FloatingOrb not visible"
    assert orb._keep_above is True, "FloatingOrb not keep_above (always-on-top failed)"
    assert orb.get_skip_taskbar_hint(), "FloatingOrb not skip_taskbar"

    # the inner OrbWidget must be drawing
    assert isinstance(orb.orb, OrbWidget)

    # Simulate a single left-click (press then release, no movement) → toggle.
    class E:
        pass

    def click():
        ev_press = E()
        ev_press.button = 1
        ev_press.x = 10.0
        ev_press.y = 10.0
        ev_press.x_root = 500.0
        ev_press.y_root = 500.0
        orb._on_press(orb, ev_press)
        ev_release = E()
        ev_release.button = 1
        ev_release.x = 10.0
        ev_release.y = 10.0
        ev_release.x_root = 500.0
        ev_release.y_root = 500.0
        orb._on_release(orb, ev_release)

    click()
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    assert toggled["n"] == 1, f"click did not toggle main (got {toggled['n']})"

    # Simulate a drag (press + move >5px + release) → must NOT toggle again.
    ev_press = E()
    ev_press.button = 1
    ev_press.x = 10.0
    ev_press.y = 10.0
    ev_press.x_root = 500.0
    ev_press.y_root = 500.0
    orb._on_press(orb, ev_press)
    ev_move = E()
    ev_move.x = 40.0
    ev_move.y = 40.0
    ev_move.x_root = 530.0
    ev_move.y_root = 530.0
    orb._on_motion(orb, ev_move)
    ev_release = E()
    ev_release.button = 1
    ev_release.x = 40.0
    ev_release.y = 40.0
    ev_release.x_root = 530.0
    ev_release.y_root = 530.0
    orb._on_release(orb, ev_release)
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    assert toggled["n"] == 1, f"drag incorrectly triggered toggle (got {toggled['n']})"

    orb.orb.stop_animation()
    orb.destroy()
    print("OK FloatingOrb: visible, keep_above, click=toggle, drag=no-toggle")


if __name__ == "__main__":
    test_floating_orb()
    print("SLICE 2 PASS")
