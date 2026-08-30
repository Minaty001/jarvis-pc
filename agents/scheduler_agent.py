"""
Scheduler Agent — Cron-like recurring task execution.
"""

import asyncio
from typing import Any, Callable, Optional

from config.logger import get_logger
from agents.base import AgentResult, BaseAgent

logger = get_logger("agents.scheduler")


class SchedulerAgent(BaseAgent):
    """Agent that runs tasks on a schedule."""

    def __init__(self, name: str = "scheduler-agent"):
        super().__init__(name=name)
        self._schedules: list[dict] = []

    def add_schedule(self, interval_sec: float, callback: Callable, name: str = "scheduled-task"):
        """Add a recurring task."""
        self._schedules.append({
            "interval": interval_sec,
            "callback": callback,
            "name": name,
            "last_run": 0,
        })
        logger.info("Scheduled: %s (every %.0fs)", name, interval_sec)

    async def run(self, **kwargs) -> AgentResult:
        logger.info("Scheduler started with %d tasks", len(self._schedules))

        try:
            while self.is_running:
                now = asyncio.get_event_loop().time()
                for sched in self._schedules:
                    if now - sched["last_run"] >= sched["interval"]:
                        sched["last_run"] = now
                        try:
                            if asyncio.iscoroutinefunction(sched["callback"]):
                                await sched["callback"]()
                            else:
                                sched["callback"]()
                        except Exception as e:
                            logger.error("Scheduled task '%s' failed: %s", sched["name"], e)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

        return AgentResult(success=True, output="Scheduler stopped")
