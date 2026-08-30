"""
Workflow Monitor — Tracks running tasks, plans, and their progress.
Detects stuck/failed workflows and publishes status events.
"""

import asyncio
import time
from typing import Optional

from config.logger import get_logger
from perception.event_bus import event_bus
from perception.event_models import Event, EventType, EventSeverity, make_event

logger = get_logger("perception.workflow_monitor")


class WorkflowMonitor:
    """Monitors active workflows and their lifecycle."""

    def __init__(self, check_interval: float = 5.0, stuck_threshold: float = 300.0):
        self.check_interval = check_interval
        self.stuck_threshold = stuck_threshold  # 5 min
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._active_workflows: dict[str, dict] = {}
        self._completed_workflows: list[dict] = []
        self._max_completed = 200

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Workflow monitor started (interval=%.1fs)", self.check_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Workflow monitor stopped")

    def register_workflow(self, workflow_id: str, name: str, metadata: Optional[dict] = None) -> None:
        """Register a new workflow for monitoring."""
        self._active_workflows[workflow_id] = {
            "id": workflow_id,
            "name": name,
            "status": "running",
            "started_at": time.time(),
            "last_update": time.time(),
            "steps_total": 0,
            "steps_completed": 0,
            "metadata": metadata or {},
            "errors": [],
        }
        logger.info("Workflow registered: %s (%s)", name, workflow_id)

    def update_workflow(
        self,
        workflow_id: str,
        status: Optional[str] = None,
        step_completed: bool = False,
        error: Optional[str] = None,
    ) -> None:
        """Update a workflow's status."""
        if workflow_id not in self._active_workflows:
            return

        wf = self._active_workflows[workflow_id]
        wf["last_update"] = time.time()

        if status:
            wf["status"] = status

        if step_completed:
            wf["steps_completed"] += 1

        if error:
            wf["errors"].append({"time": time.time(), "error": error})

    def complete_workflow(self, workflow_id: str, success: bool = True) -> None:
        """Mark a workflow as completed."""
        if workflow_id not in self._active_workflows:
            return

        wf = self._active_workflows.pop(workflow_id)
        wf["status"] = "completed" if success else "failed"
        wf["completed_at"] = time.time()
        wf["duration"] = wf["completed_at"] - wf["started_at"]

        self._completed_workflows.append(wf)
        if len(self._completed_workflows) > self._max_completed:
            self._completed_workflows = self._completed_workflows[-self._max_completed:]

        logger.info("Workflow completed: %s (%s, %.1fs)", wf["name"], wf["status"], wf["duration"])

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                await self._check_stuck_workflows()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Workflow monitor error: %s", e)
                await asyncio.sleep(self.check_interval)

    async def _check_stuck_workflows(self) -> None:
        """Check for workflows that haven't updated in a while."""
        now = time.time()
        for wf_id, wf in list(self._active_workflows.items()):
            elapsed = now - wf["last_update"]
            if elapsed > self.stuck_threshold:
                await event_bus.publish(make_event(
                    EventType.TASK, "workflow_monitor",
                    {
                        "workflow_id": wf_id,
                        "name": wf["name"],
                        "status": "stuck",
                        "elapsed_seconds": elapsed,
                    },
                    EventSeverity.WARNING,
                ))

    def get_active(self) -> list[dict]:
        """Get all active workflows."""
        return list(self._active_workflows.values())

    def get_recent_completed(self, limit: int = 10) -> list[dict]:
        """Get recently completed workflows."""
        return self._completed_workflows[-limit:]

    def get_summary(self) -> str:
        active = len(self._active_workflows)
        completed = len(self._completed_workflows)
        return f"Active: {active} | Completed: {completed}"


workflow_monitor = WorkflowMonitor()
