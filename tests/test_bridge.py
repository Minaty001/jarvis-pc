"""Slice 4 test: UIBridge — binds engine to UI; chat reaches process_goal; polls fire."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gi.repository import Gtk, GLib

from ui.bridge import UIBridge


class StubWorldState:
    task_status = "idle"
    current_goal = ""


class StubSystemMonitor:
    def get_snapshot(self):
        return {"cpu_percent": 12.0, "memory_percent": 33.0, "disk_percent": 55.0,
                "network_connected": True}


class StubOrchestrator:
    def __init__(self):
        self.calls = []

    async def process_goal(self, goal, session_id="default", task_id=None):
        self.calls.append((goal, session_id))
        return {"status": "completed", "result": {"results": [{"result": f"Echo: {goal}"}]},
                "duration_sec": 0.1}


class StubEngine:
    def __init__(self):
        self.orchestrator = StubOrchestrator()
        self.world_state = StubWorldState()
        self.system_monitor = StubSystemMonitor()
        self.event_bus = None
        self.proactive_engine = None
        self.llm_gateway = None


def test_bridge():
    engine = StubEngine()
    bridge = UIBridge(engine)

    # exercise the tools-summary path by registering one tool
    from tools.registry import tool_registry, ToolDef, ToolCategory, RiskLevel
    tool_registry.register(ToolDef(
        name="demo_tool", description="demo", category=ToolCategory.COMPUTER,
        risk_level=RiskLevel.LOW, handler=lambda **k: None,
        parameters={}))

    seen = {"orb": [], "status": [], "chat": [], "system": [], "tools": [], "memory": []}
    bridge.on_orb_state = lambda s: seen["orb"].append(s)
    bridge.on_status = lambda t: seen["status"].append(t)
    bridge.on_chat = lambda r, t: seen["chat"].append((r, t))
    bridge.on_system = lambda m: seen["system"].append(m)
    bridge.on_tools = lambda t: seen["tools"].append(t)
    bridge.on_memory = lambda t: seen["memory"].append(t)

    bridge.start()

    # wait for at least one poll tick (1 Hz) and process GTK idle queue
    for _ in range(40):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        import time
        time.sleep(0.03)

    # poll should have produced system + orb updates
    assert seen["system"], "system poll never fired"
    assert seen["orb"], "orb state never fired"
    assert seen["tools"], "tools summary never fired"

    # send chat → should reach orchestrator.process_goal
    bridge.send_chat("hello jarvis")
    for _ in range(40):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        import time
        time.sleep(0.03)
    assert engine.orchestrator.calls == [("hello jarvis", "ui")], \
        f"orchestrator not called correctly: {engine.orchestrator.calls}"
    # a chat 'user' row and a 'jarvis' reply row
    roles = [r for r, _ in seen["chat"]]
    assert "user" in roles and "jarvis" in roles, f"chat roles = {roles}"

    bridge.stop()
    print("OK UIBridge: poll fires, chat → process_goal, reply streamed to UI")


if __name__ == "__main__":
    test_bridge()
    print("SLICE 4 PASS")
