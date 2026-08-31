# task_engine/scheduler.py
"""Durable Scheduler — APScheduler with SQLite persistence, survives restarts."""
from __future__ import annotations
import asyncio, time
from typing import Any, Callable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from config.logger import get_logger
from task_engine.models import Schedule, TriggerType, MissedPolicy

logger = get_logger("task_engine.scheduler")


class DurableScheduler:
    """Wraps APScheduler with DB-persisted schedule metadata."""

    def __init__(self, timezone: str = "Asia/Kolkata"):
        self._scheduler = AsyncIOScheduler(timezone=timezone)
        self._job_map: dict[str, str] = {}  # sched_id -> apscheduler job_id
        self._timezone = timezone

    async def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("DurableScheduler started")

    async def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("DurableScheduler stopped")

    def add_schedule(self, sched: Schedule, callback: Callable) -> str:
        """Add an APScheduler job for this schedule. Returns job_id."""
        trigger = self._make_trigger(sched)
        job = self._scheduler.add_job(
            callback,
            trigger=trigger,
            id=sched.id,
            replace_existing=True,
            misfire_grace_time=300 if sched.missed_policy != MissedPolicy.SKIP_IF_MISSED else 1,
            coalesce=True,  # run once if many misfires
        )
        self._job_map[sched.id] = job.id
        logger.info("Scheduled job %s (%s)", sched.id, sched.trigger_type.value)
        return job.id

    def remove_schedule(self, sched_id: str) -> None:
        job_id = self._job_map.pop(sched_id, sched_id)
        try:
            self._scheduler.remove_job(job_id)
            logger.info("Removed schedule %s", sched_id)
        except Exception:
            pass

    def disable(self, sched_id: str) -> None:
        job_id = self._job_map.get(sched_id, sched_id)
        try:
            self._scheduler.pause_job(job_id)
        except Exception:
            pass

    def enable(self, sched_id: str) -> None:
        job_id = self._job_map.get(sched_id, sched_id)
        try:
            self._scheduler.resume_job(job_id)
        except Exception:
            pass

    def list_upcoming(self, n: int = 10) -> list[dict]:
        jobs = sorted(
            [j for j in self._scheduler.get_jobs() if j.next_run_time],
            key=lambda j: j.next_run_time,
        )
        return [
            {"job_id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
            for j in jobs[:n]
        ]

    async def load_from_db(self, repo, callback_factory: Callable[[str], Callable]) -> None:
        """Load enabled schedules from DB on startup."""
        scheds = await repo.list_schedules(enabled_only=True)
        for sched in scheds:
            cb = callback_factory(sched.task_id)
            if cb:
                self.add_schedule(sched, cb)
        logger.info("Loaded %d schedules from DB", len(scheds))

    def _make_trigger(self, sched: Schedule):
        if sched.trigger_type == TriggerType.CRON:
            parts = sched.recurrence.split()
            if len(parts) == 5:
                minute, hour, day, month, day_of_week = parts
                return CronTrigger(
                    minute=minute, hour=hour, day=day,
                    month=month, day_of_week=day_of_week,
                    timezone=sched.timezone or self._timezone,
                )
        elif sched.trigger_type == TriggerType.INTERVAL:
            seconds = float(sched.recurrence)
            return IntervalTrigger(seconds=seconds)
        elif sched.trigger_type == TriggerType.ONCE:
            import datetime
            run_at = datetime.datetime.fromtimestamp(sched.next_run_at, tz=datetime.timezone.utc)
            return DateTrigger(run_date=run_at)
        raise ValueError(f"Unsupported trigger_type: {sched.trigger_type}")


durable_scheduler = DurableScheduler()
