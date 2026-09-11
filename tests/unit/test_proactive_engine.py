"""Unit tests for ProactiveEngine and proactive rules."""

import pytest
from unittest.mock import MagicMock
from jarvis.proactive.engine import ProactiveContext, ProactiveRule, ProactiveEngine
from jarvis.config.settings import Settings


def test_proactive_context_refresh():
    ctx = ProactiveContext()
    ctx.refresh()
    assert 0.0 <= ctx.cpu_percent <= 100.0
    assert 0.0 <= ctx.ram_percent <= 100.0
    assert 0.0 <= ctx.disk_percent <= 100.0
    assert ctx.time_of_day in ("morning", "afternoon", "evening", "night")


def test_proactive_rule_cooldown():
    ctx = ProactiveContext()
    triggered = []

    rule = ProactiveRule(
        name="test_rule",
        condition=lambda c: True,
        action=lambda c: triggered.append(1),
        cooldown=100.0,
    )

    # First check: can trigger
    assert rule.can_trigger(ctx) is True

    # Execute
    import asyncio
    asyncio.run(rule.execute(ctx))
    assert len(triggered) == 1
    assert rule.trigger_count == 1

    # Second check: in cooldown
    assert rule.can_trigger(ctx) is False


@pytest.mark.asyncio
async def test_proactive_engine_evaluation(monkeypatch):
    custom_settings = Settings(
        proactive_ram_threshold=85.0,
        proactive_disk_threshold=90.0,
        proactive_cpu_threshold=90.0,
    )
    engine = ProactiveEngine(settings=custom_settings)

    # Mock context metrics: high RAM (88%), normal Disk (50%), normal CPU (20%)
    engine._context.ram_percent = 88.0
    engine._context.disk_percent = 50.0
    engine._context.cpu_percent = 20.0
    engine._context.time_of_day = "afternoon"

    # Avoid actual notification during test
    monkeypatch.setattr("jarvis.proactive.engine.notify", lambda *a, **kw: True)

    # Bypass refresh to use our mocked values
    monkeypatch.setattr(engine._context, "refresh", lambda: None)

    triggered = await engine.check_rules_once()
    assert "high_memory" in triggered
    assert "low_disk" not in triggered

    # Second check should trigger nothing because of cooldown
    triggered_again = await engine.check_rules_once()
    assert len(triggered_again) == 0


@pytest.mark.asyncio
async def test_proactive_engine_start_stop():
    engine = ProactiveEngine()
    assert engine.is_running is False

    await engine.start()
    assert engine.is_running is True

    await engine.stop()
    assert engine.is_running is False


def test_proactive_engine_list_rules():
    engine = ProactiveEngine()
    rules = engine.list_rules()
    names = [r["name"] for r in rules]
    assert "high_memory" in names
    assert "low_disk" in names
    assert "runaway_cpu" in names
    assert "morning_briefing" in names
