# task_engine/nl_parser.py
"""Natural Language Schedule Parser — converts human text into structured Schedule objects."""
from __future__ import annotations
import re, time
from datetime import datetime, timezone as dt_tz, timedelta
from typing import Optional
import dateparser
from config.logger import get_logger
from task_engine.models import Schedule, TriggerType, MissedPolicy

logger = get_logger("task_engine.nl_parser")

# Weekday cron mapping
_WEEKDAY_MAP = {
    "monday": "1", "tuesday": "2", "wednesday": "3",
    "thursday": "4", "friday": "5", "saturday": "6", "sunday": "0",
}
_WEEKDAY_PAT = re.compile(r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", re.I)
_INTERVAL_PAT = re.compile(r"every\s+(\d+)\s+(second|minute|hour|day)s?", re.I)
_WEEKDAY_LABEL_PAT = re.compile(r"every\s+weekday", re.I)
_WEEKEND_PAT = re.compile(r"every\s+weekend", re.I)
_DAILY_PAT = re.compile(r"every\s+(?:day|morning|evening|night)", re.I)
_AT_TIME_PAT = re.compile(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.I)


def _extract_hm(text: str) -> tuple[int, int]:
    """Extract hour and minute from text like 'at 8 AM' or 'at 21:30'."""
    m = _AT_TIME_PAT.search(text)
    if not m:
        return 8, 0
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    ampm = (m.group(3) or "").lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    return hour, minute


def _next_cron_run(cron_expr: str, tz: str) -> float:
    try:
        from croniter import croniter
        import pytz
        tz_obj = pytz.timezone(tz)
        now = datetime.now(tz_obj)
        c = croniter(cron_expr, now)
        return c.get_next(datetime).timestamp()
    except Exception:
        return time.time() + 3600


class NLScheduleParser:
    """Converts natural language schedule strings into Schedule objects."""

    def __init__(self, default_tz: str = "Asia/Kolkata"):
        self.default_tz = default_tz

    def parse(self, text: str, task_id: str, tz: Optional[str] = None) -> Schedule:
        tz = tz or self.default_tz
        text_clean = text.strip()
        text_lower = text_clean.lower()

        # ── Interval: "every N minutes/hours" ──────────────────────────────
        m = _INTERVAL_PAT.search(text_lower)
        if m:
            n, unit = int(m.group(1)), m.group(2).lower()
            seconds = n * {"second": 1, "minute": 60, "hour": 3600, "day": 86400}[unit]
            sched = Schedule(
                task_id=task_id,
                trigger_type=TriggerType.INTERVAL,
                recurrence=str(seconds),
                timezone=tz,
                next_run_at=time.time() + seconds,
                raw_nl=text_clean,
            )
            logger.info("Parsed interval schedule: %ds", seconds)
            return sched

        hour, minute = _extract_hm(text_lower)

        # ── Weekdays Mon-Fri ────────────────────────────────────────────────
        if _WEEKDAY_LABEL_PAT.search(text_lower):
            cron = f"{minute} {hour} * * 1-5"
            return Schedule(
                task_id=task_id, trigger_type=TriggerType.CRON, recurrence=cron,
                timezone=tz, next_run_at=_next_cron_run(cron, tz), raw_nl=text_clean,
            )

        # ── Specific weekday ────────────────────────────────────────────────
        wd_m = _WEEKDAY_PAT.search(text_lower)
        if wd_m and re.search(r"every", text_lower):
            dow = _WEEKDAY_MAP[wd_m.group(1).lower()]
            cron = f"{minute} {hour} * * {dow}"
            return Schedule(
                task_id=task_id, trigger_type=TriggerType.CRON, recurrence=cron,
                timezone=tz, next_run_at=_next_cron_run(cron, tz), raw_nl=text_clean,
            )

        # ── Weekends Sat-Sun ────────────────────────────────────────────────
        if _WEEKEND_PAT.search(text_lower):
            cron = f"{minute} {hour} * * 6,0"
            return Schedule(
                task_id=task_id, trigger_type=TriggerType.CRON, recurrence=cron,
                timezone=tz, next_run_at=_next_cron_run(cron, tz), raw_nl=text_clean,
            )

        # ── Daily ───────────────────────────────────────────────────────────
        if _DAILY_PAT.search(text_lower):
            cron = f"{minute} {hour} * * *"
            return Schedule(
                task_id=task_id, trigger_type=TriggerType.CRON, recurrence=cron,
                timezone=tz, next_run_at=_next_cron_run(cron, tz), raw_nl=text_clean,
            )

        # ── One-shot: "tomorrow morning", "at 6 PM today" ──────────────────
        parsed_dt = dateparser.parse(
            text_clean,
            settings={"TIMEZONE": tz, "RETURN_AS_TIMEZONE_AWARE": True, "PREFER_DATES_FROM": "future"},
        )
        if parsed_dt and parsed_dt.timestamp() > time.time():
            return Schedule(
                task_id=task_id, trigger_type=TriggerType.ONCE,
                timezone=tz, next_run_at=parsed_dt.timestamp(), raw_nl=text_clean,
            )

        # Fallback: run in 1 hour
        logger.warning("Could not parse schedule '%s', defaulting to 1 hour", text_clean)
        return Schedule(
            task_id=task_id, trigger_type=TriggerType.ONCE,
            timezone=tz, next_run_at=time.time() + 3600, raw_nl=text_clean,
        )


nl_parser = NLScheduleParser()
