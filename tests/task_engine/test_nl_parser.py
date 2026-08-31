# tests/task_engine/test_nl_parser.py
import pytest, time
from task_engine.nl_parser import NLScheduleParser
from task_engine.models import TriggerType

parser = NLScheduleParser(default_tz="Asia/Kolkata")

def test_weekday_at_8am():
    sched = parser.parse("every weekday at 8 AM", task_id="t-1")
    assert sched.trigger_type == TriggerType.CRON
    assert "8" in sched.recurrence
    assert sched.next_run_at is not None

def test_daily_at_9pm():
    sched = parser.parse("every day at 9 PM", task_id="t-1")
    assert sched.trigger_type == TriggerType.CRON
    assert "21" in sched.recurrence

def test_every_30_minutes():
    sched = parser.parse("every 30 minutes", task_id="t-1")
    assert sched.trigger_type == TriggerType.INTERVAL
    assert sched.recurrence == "1800"  # seconds

def test_once_tomorrow_morning():
    sched = parser.parse("tomorrow morning at 9", task_id="t-1")
    assert sched.trigger_type == TriggerType.ONCE
    assert sched.next_run_at > time.time()

def test_weekly_sunday():
    sched = parser.parse("every Sunday at 10 AM", task_id="t-1")
    assert sched.trigger_type == TriggerType.CRON
    assert "0" in sched.recurrence or "sun" in sched.recurrence.lower()

def test_raw_nl_preserved():
    sched = parser.parse("Every Friday at 6 PM", task_id="t-1")
    assert sched.raw_nl == "Every Friday at 6 PM"
