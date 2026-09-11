"""Builtin agent tools for Agenda, Countdown Timers, and Scheduled Reminders."""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from jarvis.scheduler.agenda_engine import get_agenda_engine

logger = logging.getLogger(__name__)


def set_timer(duration: str, label: str = "Timer") -> str:
    """Set a countdown timer with duration (e.g. '10m', '45s', '1h 30m', 'in 5 minutes')."""
    engine = get_agenda_engine()
    item_id, target_dt, sec = engine.set_timer(duration, label=label)
    time_str = target_dt.strftime("%I:%M:%S %p")
    return f"Timer #{item_id} set for '{label.strip() or 'Timer'}' ({duration}, due at {time_str})."


def create_reminder(when: str, title: str, recurring: Optional[str] = None) -> str:
    """Create a scheduled reminder (e.g. 'tomorrow at 3pm', 'in 2 hours', 'today at 6pm')."""
    engine = get_agenda_engine()
    item_id, target_dt, sec = engine.add_reminder(when, title=title, recurring=recurring)
    time_str = target_dt.strftime("%A, %B %d at %I:%M %p")
    rec_str = f" [Recurring: {recurring}]" if recurring else ""
    return f"Reminder #{item_id} scheduled for '{title}' on {time_str}{rec_str}."


def list_agenda(include_completed: bool = False) -> str:
    """List scheduled reminders, active countdown timers, and calendar events."""
    engine = get_agenda_engine()
    status_filter = None if include_completed else "pending"
    items = engine.list_agenda(status=status_filter)

    if not items:
        return "No pending reminders or active timers found on your agenda."

    lines = [f"JARVIS Agenda & Active Timers ({len(items)} items):"]
    lines.append("=" * 65)
    for it in items:
        due_dt = datetime.datetime.fromtimestamp(it.due_timestamp)
        due_str = due_dt.strftime("%Y-%m-%d %I:%M %p")
        status_tag = f"[{it.status.upper()}]"
        rec_tag = f" (Recurring: {it.recurring})" if it.recurring else ""
        lines.append(f"• #{it.id:<3} [{it.item_type.upper():<8}] {it.title:<24} | Due: {due_str} {status_tag}{rec_tag}")
    lines.append("=" * 65)

    return "\n".join(lines)


def cancel_agenda_item(item_id: int) -> str:
    """Cancel an active timer or scheduled reminder by ID."""
    engine = get_agenda_engine()
    ok = engine.cancel_item(item_id)
    if ok:
        return f"Agenda item #{item_id} successfully cancelled."
    return f"Agenda item #{item_id} was not found or could not be cancelled."
