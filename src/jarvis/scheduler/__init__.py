"""Proactive automation: a thin AsyncIOScheduler wrapper for Application.

Gives scheduled one-shot and recurring jobs (reminders, reports) running on the
app's own event loop — no Celery, no separate worker.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

JobFunc = Callable[..., Awaitable[None] | None]


class SchedulerManager:
    """AsyncIOScheduler lifecycle + convenience schedule methods."""

    def __init__(self) -> None:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        self._scheduler = AsyncIOScheduler()
        self._started = False

    @property
    def jobs(self) -> list:
        return self._scheduler.get_jobs()

    async def start(self) -> None:
        if self._started:
            return
        self._scheduler.start()
        self._started = True
        logger.info("Scheduler started (%d jobs)", len(self.jobs))

    async def stop(self) -> None:
        if not self._started:
            return
        self._scheduler.shutdown(wait=False)
        self._started = False
        logger.info("Scheduler stopped")

    def at(self, when: datetime, func: JobFunc, id: str | None = None) -> str:
        """Run `func` once at `when`."""
        return self._scheduler.add_job(func, "date", run_date=when, id=id)

    def every(
        self,
        interval: timedelta,
        func: JobFunc,
        id: str | None = None,
        start: datetime | None = None,
    ) -> str:
        """Run `func` repeatedly every `interval`, optionally starting at `start`."""
        return self._scheduler.add_job(
            func, "interval", seconds=interval.total_seconds(), id=id, start_date=start
        )