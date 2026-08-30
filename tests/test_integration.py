"""
Integration Tests — Validates core cognitive engine components work together.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_memory_system():
    """Test all 6 memory types."""
    from memory.working_memory import WorkingMemory
    from memory.episodic_memory import EpisodicMemory
    from memory.semantic_memory import SemanticMemory
    from memory.procedural_memory import ProceduralMemory
    from memory.preference_memory import PreferenceMemory
    from memory.failure_memory import FailureMemory

    # Working memory
    wm = WorkingMemory()
    wm.set("task", "test")
    assert wm.get("task") == "test"
    wm.delete("task")
    assert wm.get("task") is None
    print("  working_memory: OK")

    # Episodic memory
    em = EpisodicMemory()
    ep_id = em.remember("tested something", outcome="success", tags=["test"])
    assert ep_id.startswith("ep-")
    results = em.retrieve(query="tested")
    assert len(results) > 0
    print("  episodic_memory: OK")

    # Semantic memory
    sm = SemanticMemory()
    fact_id = sm.remember("Python is a programming language", category="tech")
    assert fact_id.startswith("sem-")
    results = sm.retrieve(query="Python")
    assert len(results) > 0
    print("  semantic_memory: OK")

    # Procedural memory
    pm = ProceduralMemory()
    proc_id = pm.remember("restart service", ["stop", "start"], context="systemd")
    assert proc_id.startswith("proc-")
    print("  procedural_memory: OK")

    # Preference memory
    prefm = PreferenceMemory()
    pref_id = prefm.remember("dark_mode", True, category="ui")
    assert prefm.get("dark_mode") == True
    print("  preference_memory: OK")

    # Failure memory
    fm = FailureMemory()
    fail_id = fm.remember("deploy", "timeout", cause="network")
    assert fail_id.startswith("fail-")
    print("  failure_memory: OK")


def test_event_bus():
    """Test event bus pub/sub."""
    from perception.event_bus import EventBus
    from perception.event_models import Event, EventType

    bus = EventBus(dedup_window_sec=0.1)

    received = []

    async def handler(event):
        received.append(event)

    bus.subscribe(EventType.SYSTEM, handler)

    async def run():
        await bus.start()
        event = Event(type=EventType.SYSTEM, source="test", payload={"msg": "hello"})
        await bus.publish(event)
        await asyncio.sleep(0.2)
        await bus.stop()

    asyncio.run(run())
    assert len(received) > 0
    print("  event_bus: OK")


def test_tool_registry():
    """Test tool registry and security."""
    from tools.registry import ToolRegistry, ToolDef, ToolCategory, RiskLevel
    from tools.security import SecurityPolicy

    reg = ToolRegistry()

    async def dummy_handler(**kwargs):
        return "ok"

    tool = ToolDef(
        name="test_tool",
        description="A test tool",
        category=ToolCategory.CUSTOM,
        risk_level=RiskLevel.LOW,
        handler=dummy_handler,
    )
    reg.register(tool)
    assert reg.get("test_tool") is not None
    assert len(reg.list_tools()) == 1

    can, _ = reg.can_call("test_tool")
    assert can == True

    # Security policy
    policy = SecurityPolicy(strict_mode=True)
    allowed, reason, _ = policy.evaluate(tool, {"arg": "value"})
    assert allowed == True

    # Blocked pattern
    allowed, reason, _ = policy.evaluate(tool, {"command": "rm -rf /"})
    assert allowed == False
    print("  tool_registry + security: OK")


def test_proactive_engine():
    """Test proactive rules."""
    from proactive.engine import ProactiveEngine, ProactiveRule

    engine = ProactiveEngine(check_interval=0.1)

    triggered = []

    async def test_action(ctx):
        triggered.append(True)
        return "test fired"

    rule = ProactiveRule(
        name="test_rule",
        condition=lambda ctx: True,
        action=test_action,
        cooldown=0,
    )
    engine.add_rule(rule)

    async def run():
        await engine.start()
        await asyncio.sleep(0.3)
        await engine.stop()

    asyncio.run(run())
    assert len(triggered) > 0
    print("  proactive_engine: OK")


def test_observability():
    """Test metrics and tracer."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("observability", "core/observability.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    m = mod.MetricsCollector()
    m.inc("test_counter", 5)
    m.set("test_gauge", 42.0)
    m.timer("test_timer", 0.1)
    assert m.get_counter("test_counter") == 5
    assert m.get_gauge("test_gauge") == 42.0
    stats = m.get_timer_stats("test_timer")
    assert stats["count"] == 1

    t = mod.Tracer()
    span = t.start_span("test_op")
    span.set_attribute("key", "value")
    duration = t.end_span(span)
    assert duration >= 0
    print("  observability: OK")


def test_cognitive_orchestrator():
    """Test orchestrator initialization."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("orchestrator", "cognitive/orchestrator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    orch = mod.CognitiveOrchestrator()
    orch.inject_dependencies(
        llm_gateway=None,
        tool_executor=None,
        event_bus=None,
        memory_manager=None,
    )
    assert orch._running == False
    print("  cognitive_orchestrator: OK")


def main():
    print("Running integration tests...\n")
    test_memory_system()
    test_event_bus()
    test_tool_registry()
    test_proactive_engine()
    test_observability()
    test_cognitive_orchestrator()
    print("\nAll tests passed!")


if __name__ == "__main__":
    main()
