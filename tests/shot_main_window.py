"""Render a screenshot PNG of the MainWindow for visual verification."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gi.repository import Gtk, Gdk

from ui import theme
from ui.main_window import MainWindow


def main():
    theme.load_css()
    win = MainWindow(on_send=lambda t: None)
    win.show_all()
    # populate with demo content
    win.set_orb_state("idle")
    win.set_orb_caption("JARVIS ONLINE")
    win.set_status("Online")
    win.add_chat("user", "Open the terminal and check disk space")
    win.add_chat("jarvis", "On it. Running `df -h` now — your root disk is at 67% used.")
    win.add_chat("system", "Task completed in 1.2s · tool: run_command")
    win.update_system({
        "cpu_percent": 18.0, "memory_percent": 44.0, "disk_percent": 67.0,
        "network_connected": True, "battery_percent": 92.0, "battery_plugged": True,
    })
    win.set_tools_summary("open_app, close_app, web_search, run_command, take_photo, set_volume (14 total)")
    win.set_memory_summary("working: 3 | episodic: 21 | semantic: 9 | preference: 4")
    win._entry.set_text("")
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)

    # grab the window pixbuf
    win.realize()
    gdk_win = win.get_window()
    w = win.get_allocated_width()
    h = win.get_allocated_height()
    pix = Gdk.pixbuf_get_from_window(gdk_win, 0, 0, w, h)
    out = os.path.join(os.path.dirname(__file__), "..", "data", "main_window.png")
    out = os.path.abspath(out)
    pix.savev(out, "png")
    print(f"screenshot -> {out}")
    win.orb.stop_animation()
    win.destroy()


if __name__ == "__main__":
    main()
