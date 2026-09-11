"""Natural language time and relative duration parser for JARVIS PC."""

from __future__ import annotations

import datetime
import re
from typing import Optional, Tuple


def parse_time_expression(expr: str, now: Optional[datetime.datetime] = None) -> Tuple[datetime.datetime, float]:
    """Parse relative duration or clock time into (target_datetime, duration_seconds).

    Supports:
    - Relative durations: '10s', '15m', '2h', '1h 30m', 'in 15 minutes', 'in 2 hours', '45 seconds'
    - Specific clock times: 'at 3:30 pm', 'at 16:00', 'at 9am', '3pm', '14:30'
    - Day offsets: 'tomorrow at 3pm', 'today at 5pm', 'tonight at 8pm'
    """
    if now is None:
        now = datetime.datetime.now()

    clean = expr.strip().lower()
    clean = re.sub(r"^(in|at|for|on)\s+", "", clean)

    # 1. Check for simple compact relative units like "10s", "15m", "2h", "1d"
    compact_match = re.match(r"^(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)$", clean)
    if compact_match:
        val = float(compact_match.group(1))
        unit = compact_match.group(2)
        if unit.startswith("s"):
            sec = val
        elif unit.startswith("m"):
            sec = val * 60.0
        elif unit.startswith("h"):
            sec = val * 3600.0
        else:
            sec = val * 86400.0
        target = now + datetime.timedelta(seconds=sec)
        return target, sec

    # 2. Check for compound relative durations (e.g. "1 hour 30 mins", "2h 15m 10s")
    dur_parts = re.findall(r"(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)", clean)
    if dur_parts and len(dur_parts) >= 1 and not re.search(r"\b(am|pm|at|tomorrow|today|tonight)\b", clean):
        total_sec = 0.0
        for val_str, unit in dur_parts:
            val = float(val_str)
            if unit.startswith("s"):
                total_sec += val
            elif unit.startswith("m"):
                total_sec += val * 60.0
            elif unit.startswith("h"):
                total_sec += val * 3600.0
            else:
                total_sec += val * 86400.0
        if total_sec > 0:
            target = now + datetime.timedelta(seconds=total_sec)
            return target, total_sec

    # 3. Check for day offset prefixes (e.g. "tomorrow at 3pm", "today at 4:30")
    day_offset = 0
    if "tomorrow" in clean:
        day_offset = 1
        clean = clean.replace("tomorrow", "").strip()
    elif "today" in clean:
        day_offset = 0
        clean = clean.replace("today", "").strip()
    elif "tonight" in clean:
        day_offset = 0
        clean = clean.replace("tonight", "").strip()

    clean = re.sub(r"^(at|for|on)\s+", "", clean).strip()

    # 4. Check for clock times: "3:30 pm", "15:00", "9am", "11:45"
    time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", clean)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        ampm = time_match.group(3)

        if ampm:
            ampm = ampm.lower()
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            target_date = (now + datetime.timedelta(days=day_offset)).date()
            target = datetime.datetime.combine(target_date, datetime.time(hour=hour, minute=minute))

            # If time is earlier than now on the same day and no day was specified, assume next day
            if target <= now and day_offset == 0:
                target += datetime.timedelta(days=1)

            diff = (target - now).total_seconds()
            return target, max(1.0, diff)

    # Fallback default: 5 minutes from now
    default_sec = 300.0
    return now + datetime.timedelta(seconds=default_sec), default_sec
