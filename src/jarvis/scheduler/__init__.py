"""Proactive automation: AsyncIOScheduler with native AsyncIO fallback for Application.

Gives scheduled one-shot and recurring jobs (reminders, reports) running on the
app's own event loop — zero external dependencies required.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)

JobFunc = Callable[..., Awaitable[None] | None]


class _AsyncioFallbackJob:
    """Represents a scheduled job in the native asyncio fallback scheduler."""

    def __init__(self, job_id: str, task: asyncio.Task[Any]) -> None:
        self.id = job_id
        self._task = task

    @property
    def name(self) -> str:
        return self.id


class _AsyncioFallbackScheduler:
    """Pure asyncio in-memory scheduler fallback when apscheduler is not installed."""

    def __init__(self) -> None:
        self._jobs: Dict[str, asyncio.Task[Any]] = {}
        self._running: bool = False

    def get_jobs(self) -> List[_AsyncioFallbackJob]:
        return [_AsyncioFallbackJob(jid, task) for jid, task in self._jobs.items() if not task.done()]

    def start(self) -> None:
        self._running = True

    def shutdown(self, wait: bool = False) -> None:
        self._running = False
        for task in self._jobs.values():
            if not task.done():
                task.cancel()
        self._jobs.clear()

    def add_job(
        self,
        func: JobFunc,
        trigger: str = "date",
        run_date: Optional[datetime] = None,
        seconds: Optional[float] = None,
        id: Optional[str] = None,
        start_date: Optional[datetime] = None,
    ) -> str:
        job_id = id or f"job-{uuid.uuid4().hex[:8]}"

        async def _job_coro() -> None:
            try:
                if trigger == "date" and run_date is not None:
                    now = datetime.now(run_date.tzinfo or None) if run_date.tzinfo else datetime.now()
                    delay = max(0.0, (run_date - now).total_seconds())
                    if delay > 0:
                        await asyncio.sleep(delay)
                    if asyncio.iscoroutinefunction(func):
                        await func()
                    else:
                        func()
                elif trigger == "interval" and seconds is not None:
                    if start_date is not None:
                        now = datetime.now(start_date.tzinfo or None) if start_date.tzinfo else datetime.now()
                        initial_delay = max(0.0, (start_date - now).total_seconds())
                        if initial_delay > 0:
                            await asyncio.sleep(initial_delay)
                    while self._running:
                        await asyncio.sleep(seconds)
                        if not self._running:
                            break
                        if asyncio.iscoroutinefunction(func):
                            await func()
                        else:
                            func()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.error("Error executing scheduled job '%s': %s", job_id, exc)
            finally:
                self._jobs.pop(job_id, None)

        task = asyncio.create_task(_job_coro())
        self._jobs[job_id] = task
        return job_id


class SchedulerManager:
    """Scheduler lifecycle + convenience schedule methods."""

    def __init__(self) -> None:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            self._scheduler = AsyncIOScheduler()
            self._is_apscheduler = True
        except ImportError:
            logger.debug("APScheduler not found; utilizing native AsyncIO fallback scheduler.")
            self._scheduler = _AsyncioFallbackScheduler()
            self._is_apscheduler = False

        self._started = False

    @property
    def jobs(self) -> list:
        return self._scheduler.get_jobs()

    async def start(self) -> None:
        if self._started:
            return
        self._scheduler.start()
        self._started = True
        logger.info("Scheduler started (%d jobs, backend=%s)", len(self.jobs), "APScheduler" if self._is_apscheduler else "AsyncIO")

    async def stop(self) -> None:
        if not self._started:
            return
        self._scheduler.shutdown(wait=False)
        self._started = False
        logger.info("Scheduler stopped")

    def at(self, when: datetime, func: JobFunc, id: str | None = None) -> str:
        """Run `func` once at `when`."""
        if self._is_apscheduler:
            return self._scheduler.add_job(func, "date", run_date=when, id=id)
        return self._scheduler.add_job(func, trigger="date", run_date=when, id=id)

    def every(
        self,
        interval: timedelta,
        func: JobFunc,
        id: str | None = None,
        start: datetime | None = None,
    ) -> str:
        """Run `func` repeatedly every `interval`, optionally starting at `start`."""
        if self._is_apscheduler:
            return self._scheduler.add_job(
                func, "interval", seconds=interval.total_seconds(), id=id, start_date=start
            )
        return self._scheduler.add_job(
            func, trigger="interval", seconds=interval.total_seconds(), id=id, start_date=start
        )