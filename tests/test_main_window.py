"""Slice 3 test: MainWindow — render, chat add, system update, send callback."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gi.repository import Gtk, Gdk

from ui import theme
from ui.main_window import MainWindow


def test_main_window():
    theme.load_css()
    sent = []

    def on_send(text):
        sent.append(text)

    win = MainWindow(on_send=on_send)
    win.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)

    # orb state + caption
    win.set_orb_state("listening")
    win.set_orb_caption("JARVIS LISTENING")
    win.set_status("Online")
    assert win.orb._state == "listening"

    # chat rows
    win.add_chat("user", "What is my CPU usage?")
    win.add_chat("jarvis", "Your CPU is at 23%. All systems nominal.")
    win.add_chat("system", "Tip: say 'Hey Jarvis' to activate voice.")
    rows = win._chat_list.get_children()
    assert len(rows) == 3, f"expected 3 chat rows, got {len(rows)}"
    labels = [r.get_child().get_children()[1 if i != 2 else 0].get_text() for i, r in enumerate(rows)]
    assert "What is my CPU usage?" in labels[0]
    assert "Your CPU is at 23%" in labels[1]

    # system update
    win.update_system({
        "cpu_percent": 23.0,
        "memory_percent": 41.0,
        "disk_percent": 67.0,
        "network_connected": True,
        "battery_percent": 88.0,
        "battery_plugged": False,
    })
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    cpu_val, _ = win._sys_vals["cpu_percent"]
    assert cpu_val.get_text() == "23%", f"cpu label = {cpu_val.get_text()}"
    bat_val, _ = win._sys_vals["battery"]
    assert bat_val.get_text().startswith("88%"), f"battery = {bat_val.get_text()}"

    # tools / memory summary
    win.set_tools_summary("open_app, web_search, take_photo (12 total)")
    win.set_memory_summary("working: 3 | episodic: 21 | semantic: 9")
    assert "web_search" in win._tools_lbl.get_text()

    # send via entry activate
    win._entry.set_text("open firefox")
    win._entry.emit("activate")
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    assert sent == ["open firefox"], f"send callback got {sent}"

    # hide (delete-event) should NOT destroy
    win.hide()
    assert win.get_visible() is False

    win.orb.stop_animation()
    print("OK MainWindow: chat rows, system update, send callback, hide works")


if __name__ == "__main__":
    test_main_window()
    print("SLICE 3 PASS")
