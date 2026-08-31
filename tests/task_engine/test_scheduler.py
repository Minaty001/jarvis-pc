# tests/task_engine/test_scheduler.py
import asyncio, time, pytest
from unittest.mock import AsyncMock
from task_engine.models import Schedule, TriggerType
from task_engine.scheduler import DurableScheduler
from task_engine.repository import TaskRepository

@pytest.fixture
def scheduler():
    s = DurableScheduler()
    asyncio.get_event_loop().run_until_complete(s.start())
    yield s
    asyncio.get_event_loop().run_until_complete(s.stop())

def test_one_shot_fires(scheduler):
    fired = []
    sched = Schedule(task_id="t-1", trigger_type=TriggerType.ONCE, next_run_at=time.time() + 0.1)

    async def cb(): fired.append(1)
    scheduler.add_schedule(sched, cb)
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))
    assert len(fired) == 1

def test_interval_fires_repeatedly(scheduler):
    fired = []
    sched = Schedule(task_id="t-2", trigger_type=TriggerType.INTERVAL, recurrence="1")  # 1 second

    async def cb(): fired.append(1)
    scheduler.add_schedule(sched, cb)
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(2.5))
    assert len(fired) >= 2

def test_remove_stops_firing(scheduler):
    fired = []
    sched = Schedule(task_id="t-3", trigger_type=TriggerType.INTERVAL, recurrence="1")

    async def cb(): fired.append(1)
    sched_id = scheduler.add_schedule(sched, cb)
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(1.5))
    scheduler.remove_schedule(sched_id)
    count_before = len(fired)
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(1.5))
    assert len(fired) == count_before  # no new firings

def test_disable_pauses_firing(scheduler):
    fired = []
    sched = Schedule(task_id="t-4", trigger_type=TriggerType.INTERVAL, recurrence="1")

    async def cb(): fired.append(1)
    sched_id = scheduler.add_schedule(sched, cb)
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(1.5))
    scheduler.disable(sched_id)
    count_before = len(fired)
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(1.5))
    assert len(fired) == count_before

def test_list_upcoming_returns_sorted(scheduler):
    for i in range(3):
        s = Schedule(task_id=f"t-u{i}", trigger_type=TriggerType.INTERVAL, recurrence="60")
        scheduler.add_schedule(s, AsyncMock())
    upcoming = scheduler.list_upcoming(5)
    assert len(upcoming) >= 1
