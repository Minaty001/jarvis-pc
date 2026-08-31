"""Slice 5 test: JarvisApp wires MainWindow + FloatingOrb + bridge + tray."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gi.repository import Gtk, GLib

from ui.app import JarvisApp


class StubOrchestrator:
    def __init__(self):
        self.calls = []

    async def process_goal(self, goal, session_id="default", task_id=None):
        self.calls.append(goal)
        return {"status": "completed", "result": {"results": [{"result": f"done: {goal}"}]},
                "duration_sec": 0.05}


class StubEngine:
    def __init__(self):
        self.orchestrator = StubOrchestrator()
        self.event_bus = None
        self.world_state = None
        self.system_monitor = None
        self.proactive_engine = None
        self.llm_gateway = None


def test_jarvis_app():
    engine = StubEngine()
    app = JarvisApp(engine=engine)
    app.register()     # GApplication registration (needed before activate)
    app.activate()  # emits startup then activate → creates windows

    # Both windows exist
    assert app.main_window is not None, "MainWindow not created"
    assert app.floating_orb is not None, "FloatingOrb not created"
    assert app.bridge is not None, "UIBridge not created"
    # bridge started
    assert app.bridge._running is True, "bridge not started"

    # floating orb visible (background watching)
    assert app.floating_orb.get_visible()

    # send a chat via main window entry
    app.main_window._entry.set_text("open firefox")
    app.main_window._entry.emit("activate")

    # process events + let bridge thread run
    import time
    for _ in range(60):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.03)

    assert engine.orchestrator.calls == ["open firefox"], \
        f"chat did not reach orchestrator: {engine.orchestrator.calls}"

    # robustly extract chat text from every row's message label
    def chat_texts():
        out = []
        for row in app.main_window._chat_list.get_children():
            box = row.get_child()
            # box children: [who label (if not system), msg label]
            msg_label = box.get_children()[-1]
            out.append(msg_label.get_text())
        return out

    texts = chat_texts()
    assert any("open firefox" in t for t in texts), "user message missing in chat"
    assert any("done: open firefox" in t for t in texts), "jarvis reply missing in chat"

    # toggle main window via floating orb click (simulate toggle callback)
    app.floating_orb._on_toggle and app.floating_orb._on_toggle()

    # quit
    app._quit()
    # let idle quit run
    for _ in range(20):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.02)
    print("OK JarvisApp: MainWindow + FloatingOrb + bridge + chat + quit")


if __name__ == "__main__":
    test_jarvis_app()
    print("SLICE 5 PASS")
