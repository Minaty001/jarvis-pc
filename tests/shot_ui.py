"""Smoke-screenshot: boot the real engine in UI mode briefly, screenshot the window."""

import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gi.repository import Gtk, Gdk, GLib

from config.logger import setup_logging
setup_logging("WARNING")


def main():
    from run import _bootstrap_engine, _run_ui_mode  # noqa
    # We can't easily run both GTK + engine here without run.py's threading;
    # instead instantiate the app directly with a live engine bundle built after bootstrap.
    import asyncio
    from cognitive.orchestrator import cognitive_orchestrator
    from perception.event_bus import event_bus
    from perception.system_monitor import system_monitor
    from proactive.engine import proactive_engine
    from llm.gateway import llm_gateway
    from cognitive.world_state import world_state
    from ui.app import JarvisApp

    # build bundle without full bootstrap (engine loop not running) — enough to render
    class B:
        pass
    bundle = B()
    bundle.orchestrator = cognitive_orchestrator
    bundle.event_bus = event_bus
    bundle.world_state = world_state
    bundle.system_monitor = system_monitor
    bundle.proactive_engine = proactive_engine
    bundle.llm_gateway = llm_gateway

    app = JarvisApp(engine=bundle)
    app.register()
    app.activate()
    app.main_window.add_chat("user", "What's my system status?")
    app.main_window.add_chat("jarvis", "CPU 18%, RAM 44%, disk 67%. All systems nominal.")
    app.main_window.update_system({
        "cpu_percent": 18.0, "memory_percent": 44.0, "disk_percent": 67.0,
        "network_connected": True, "battery_percent": 91.0, "battery_plugged": True})
    app.main_window.set_tools_summary("open_app, web_search, run_command, take_photo (14 total)")
    app.main_window.set_memory_summary("working: 3 | episodic: 21 | semantic: 9")

    while Gtk.events_pending():
        Gtk.main_iteration_do(False)

    win = app.main_window
    win.realize()
    gdk_win = win.get_window()
    w = win.get_allocated_width()
    h = win.get_allocated_height()
    pix = Gdk.pixbuf_get_from_window(gdk_win, 0, 0, w, h)
    out = os.path.join(ROOT, "data", "ui_full.png")
    pix.savev(out, "png")
    print("wrote", out)

    # also screenshot the floating orb
    fo = app.floating_orb
    fo.realize()
    fg = fo.get_window()
    fw = fo.get_allocated_width()
    fh = fo.get_allocated_height()
    pix2 = Gdk.pixbuf_get_from_window(fg, 0, 0, fw, fh)
    out2 = os.path.join(ROOT, "data", "ui_floating.png")
    pix2.savev(out2, "png")
    print("wrote", out2)

    app.bridge.stop()
    app.floating_orb.orb.stop_animation()
    app.quit()


if __name__ == "__main__":
    main()
