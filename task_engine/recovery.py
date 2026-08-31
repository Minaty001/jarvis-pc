# task_engine/recovery.py
"""Crash Recovery — detects interrupted tasks on startup and resumes or asks user."""
from __future__ import annotations
import time
from config.logger import get_logger
from task_engine.models import Task, TaskState, StepState

logger = get_logger("task_engine.recovery")

RECOVERABLE_STATES = {TaskState.RUNNING, TaskState.RETRYING, TaskState.PAUSED}
ASK_USER_STATES = {TaskState.WAITING_FOR_APPROVAL, TaskState.WAITING_FOR_INPUT}


class CrashRecovery:
    """On JARVIS startup, scans DB for unfinished tasks and determines recovery action."""

    async def recover(self, repo) -> list[dict]:
        """Scan all non-terminal tasks and return recovery action list."""
        all_tasks = await repo.list_tasks()
        actions = []

        for task in all_tasks:
            if task.is_terminal():
                continue

            if task.state in ASK_USER_STATES:
                logger.info("Task %s was waiting for user — flagging", task.id)
                actions.append({
                    "task_id": task.id,
                    "title": task.title,
                    "action": "ask_user",
                    "reason": f"Task was {task.state.value} when JARVIS last stopped",
                })
                continue

            if task.state in RECOVERABLE_STATES:
                # Find last completed step checkpoint
                checkpoints = await repo.list_checkpoints(task.id)
                completed_step_ids = {c["step_id"] for c in checkpoints}
                in_flight = [
                    s for s in task.steps
                    if s.state == StepState.RUNNING and s.id not in completed_step_ids
                ]
                # Reset in-flight steps back to PENDING so they re-run
                for s in in_flight:
                    s.state = StepState.PENDING
                    s.started_at = None
                    logger.info("Reset in-flight step %s of task %s to PENDING", s.id, task.id)

                task.transition(TaskState.READY)
                await repo.update_task(task)
                await repo.append_event(task.id, "TASK_RECOVERED", {"recovered_at": time.time()})

                actions.append({
                    "task_id": task.id,
                    "title": task.title,
                    "action": "resume",
                    "reason": f"Task was {task.state.value}; {len(completed_step_ids)} steps already done",
                })
                logger.info("Task %s queued for resume (%d steps already done)", task.id, len(completed_step_ids))

        logger.info("Crash recovery complete: %d tasks need attention", len(actions))
        return actions


crash_recovery = CrashRecovery()
