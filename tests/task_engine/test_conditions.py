# tests/task_engine/test_conditions.py
import asyncio, pytest
from unittest.mock import AsyncMock, patch
from task_engine.conditions import ConditionEngine

def test_condition_fires_when_met():
    fired = []
    engine = ConditionEngine(poll_interval=0.05)

    call_count = [0]
    def always_true(ctx): 
        call_count[0] += 1
        return call_count[0] >= 2  # fires on 2nd check

    async def action(ctx): fired.append(1)
    engine.add_condition("test_cond", always_true, action, cooldown=0)

    async def run():
        t = asyncio.create_task(engine.start())
        await asyncio.sleep(0.3)
        engine.stop()
        t.cancel()

    asyncio.get_event_loop().run_until_complete(run())
    assert len(fired) >= 1

def test_cooldown_prevents_repeat_firing():
    fired = []
    engine = ConditionEngine(poll_interval=0.05)

    def always_true(ctx): return True
    async def action(ctx): fired.append(1)
    engine.add_condition("test_cool", always_true, action, cooldown=9999)

    async def run():
        t = asyncio.create_task(engine.start())
        await asyncio.sleep(0.3)
        engine.stop()
        t.cancel()

    asyncio.get_event_loop().run_until_complete(run())
    assert len(fired) == 1  # only fires once due to cooldown

def test_battery_condition_defined():
    engine = ConditionEngine()
    names = [c["name"] for c in engine.list_conditions()]
    assert "battery_low" in names
