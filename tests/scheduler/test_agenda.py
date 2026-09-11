"""Tests for Smart Agenda, Countdown Timers, Reminders, and Daily Schedule Hub."""

import datetime
from unittest.mock import MagicMock, patch
import pytest

from jarvis.cli.main import run_cli
from jarvis.scheduler.agenda_engine import AgendaEngine
from jarvis.scheduler.agenda_store import AgendaStore
from jarvis.scheduler.time_parser import parse_time_expression
from jarvis.tools.builtin.agenda_tools import (
    cancel_agenda_item,
    create_reminder,
    list_agenda,
    set_timer,
)


# ==========================================
# Time Parser Tests
# ==========================================

def test_time_parser_relative_durations():
    base_dt = datetime.datetime(2026, 9, 15, 10, 0, 0)

    # 10s
    dt1, sec1 = parse_time_expression("10s", now=base_dt)
    assert sec1 == 10.0
    assert dt1 == datetime.datetime(2026, 9, 15, 10, 0, 10)

    # 15m
    dt2, sec2 = parse_time_expression("15m", now=base_dt)
    assert sec2 == 900.0
    assert dt2 == datetime.datetime(2026, 9, 15, 10, 15, 0)

    # 2 hours
    dt3, sec3 = parse_time_expression("in 2 hours", now=base_dt)
    assert sec3 == 7200.0
    assert dt3 == datetime.datetime(2026, 9, 15, 12, 0, 0)

    # Compound "1h 30m"
    dt4, sec4 = parse_time_expression("1h 30m", now=base_dt)
    assert sec4 == 5400.0
    assert dt4 == datetime.datetime(2026, 9, 15, 11, 30, 0)


def test_time_parser_clock_times():
    base_dt = datetime.datetime(2026, 9, 15, 10, 0, 0)

    # "at 3pm" -> 15:00 on same day
    dt1, sec1 = parse_time_expression("at 3pm", now=base_dt)
    assert dt1.hour == 15
    assert dt1.minute == 0
    assert dt1.day == 15

    # "tomorrow at 9am" -> 09:00 on next day
    dt2, sec2 = parse_time_expression("tomorrow at 9am", now=base_dt)
    assert dt2.hour == 9
    assert dt2.minute == 0
    assert dt2.day == 16


# ==========================================
# Agenda Store Tests
# ==========================================

@pytest.fixture
def temp_agenda_store(tmp_path):
    db_file = tmp_path / "agenda.db"
    return AgendaStore(db_file)


def test_agenda_store_crud(temp_agenda_store):
    store = temp_agenda_store

    now_ts = datetime.datetime.now().timestamp()
    due_ts = now_ts + 600.0

    # 1. Add timer
    tid = store.add_item("Tea Timer", due_ts, item_type="timer")
    assert tid > 0

    # 2. Add reminder
    rid = store.add_item("Team Standup", due_ts + 3600.0, item_type="reminder", recurring="daily")
    assert rid > tid

    # 3. Get item
    item = store.get_item(tid)
    assert item is not None
    assert item.title == "Tea Timer"
    assert item.status == "pending"

    # 4. List pending
    items = store.list_items(status="pending")
    assert len(items) == 2

    # 5. Get due items (with simulated current time)
    due = store.get_due_items(current_timestamp=due_ts + 10.0)
    assert len(due) == 1
    assert due[0].id == tid

    # 6. Update status
    assert store.update_status(tid, "completed") is True
    assert len(store.list_items(status="pending")) == 1

    # 7. Reschedule recurring
    assert store.reschedule_recurring(rid) is True
    rescheduled = store.get_item(rid)
    assert rescheduled.due_timestamp > due_ts + 3600.0


# ==========================================
# Agenda Engine & Alert Tests
# ==========================================

def test_agenda_engine_workflow(temp_agenda_store):
    store = temp_agenda_store
    alerts_fired = []

    engine = AgendaEngine(store=store, on_alert=lambda item: alerts_fired.append(item))

    # Set 10s timer
    tid, target_dt, sec = engine.set_timer("10s", label="Egg boiling")
    assert tid > 0
    assert sec == 10.0

    # Schedule reminder
    rid, r_dt, r_sec = engine.add_reminder("tomorrow at 2pm", title="Doctor Appointment")
    assert rid > 0

    # List agenda
    pending = engine.list_agenda()
    assert len(pending) == 2

    # Simulate due items processing
    with patch("jarvis.scheduler.agenda_engine.notify") as mock_notify, \
         patch("jarvis.scheduler.agenda_engine.speak_interruptible") as mock_speak:
        
        # Advance store item timestamp into past
        store._conn.execute("UPDATE agenda_items SET due_timestamp = ? WHERE id = ?", (100.0, tid))
        store._conn.commit()

        processed = engine.process_due_items()
        assert len(processed) == 1
        assert processed[0].id == tid
        assert len(alerts_fired) == 1

        mock_notify.assert_called_once()
        assert "Egg boiling" in mock_notify.call_args[0][1]


# ==========================================
# Agent Tools Tests
# ==========================================

def test_builtin_agenda_tools(temp_agenda_store):
    with patch("jarvis.scheduler.agenda_engine._ENGINE_INSTANCE", AgendaEngine(store=temp_agenda_store)):
        # 1. set_timer
        res1 = set_timer("5m", label="Pizza in oven")
        assert "Timer #" in res1
        assert "Pizza in oven" in res1

        # 2. create_reminder
        res2 = create_reminder("tomorrow at 4pm", title="Dentist visit")
        assert "Reminder #" in res2
        assert "Dentist visit" in res2

        # 3. list_agenda
        res3 = list_agenda()
        assert "JARVIS Agenda & Active Timers" in res3
        assert "Pizza in oven" in res3
        assert "Dentist visit" in res3

        # 4. cancel_agenda_item
        res4 = cancel_agenda_item(1)
        assert "successfully cancelled" in res4


# ==========================================
# CLI Subcommands Tests
# ==========================================

def test_cli_timer_and_agenda_commands(temp_agenda_store, capsys):
    engine = AgendaEngine(store=temp_agenda_store)
    with patch("jarvis.scheduler.agenda_engine.get_agenda_engine", return_value=engine):
        # Timer
        ret1 = run_cli(["timer", "15m", "Pasta"])
        assert ret1 == 0
        captured = capsys.readouterr()
        assert "Countdown Timer #1" in captured.out
        assert "Pasta" in captured.out

        # Agenda Add
        ret2 = run_cli(["agenda", "add", "tomorrow at 10am", "Project Sync"])
        assert ret2 == 0
        captured = capsys.readouterr()
        assert "Scheduled Reminder #2" in captured.out
        assert "Project Sync" in captured.out

        # Agenda List
        ret3 = run_cli(["agenda", "list"])
        assert ret3 == 0
        captured = capsys.readouterr()
        assert "Pasta" in captured.out
        assert "Project Sync" in captured.out

        # Agenda Cancel
        ret4 = run_cli(["agenda", "cancel", "1"])
        assert ret4 == 0
        captured = capsys.readouterr()
        assert "Agenda item #1 cancelled" in captured.out
