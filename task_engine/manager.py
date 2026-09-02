# task_engine/manager.py
"""Task Manager — Single canonical entry point for all task creation and control."""
from __future__ import annotations
import asyncio, time
from typing import Optional, TYPE_CHECKING
from config.logger import get_logger
from task_engine.models import (
    Task, TaskState, TaskStep, Schedule, TaskPriority, StepState, ActionResult
)
from task_engine.repository import TaskRepository, task_repository
from task_engine.dag_executor import DAGExecutor
from task_engine.scheduler import DurableScheduler, durable_scheduler
from task_engine.nl_parser import NLScheduleParser, nl_parser
from task_engine.approval import ApprovalEngine, approval_engine
from task_engine.recovery import CrashRecovery, crash_recovery

if TYPE_CHECKING:
    from jarvis.tools.executor import ToolExecutor

logger = get_logger("task_engine.manager")


class TaskManager:
    """Single canonical entry point for all task submission, scheduling, and control."""

    def __init__(self, tool_executor: ToolExecutor | None = None):
        self._tool_executor = tool_executor
        self._repo: TaskRepository = task_repository
        self._scheduler: DurableScheduler = durable_scheduler
        self._nl_parser: NLScheduleParser = nl_parser
        self._approval: ApprovalEngine = approval_engine
        self._recovery: CrashRecovery = crash_recovery
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._notify_cb = None  # set by UI/voice bridge

    async def _step_runner(self, action: str, params: dict, context=None) -> ActionResult:
        """Dispatches through the injected ToolExecutor."""
        if self._tool_executor is None:
            return ActionResult.fail("No ToolExecutor configured")
        from jarvis.cognitive.context import ExecutionContext
        ctx = context or ExecutionContext(
            session_id="task-engine",
            task_id="task-step",
            user_id="system",
            request_id="task-engine-req",
            permissions=frozenset({"filesystem.read", "filesystem.write", "desktop.applications", "system.read", "media.camera"}),
        )
        try:
            res = await self._tool_executor.execute(action, context=ctx, arguments=params)
            return ActionResult.ok(str(res))
        except Exception as e:
            return ActionResult.fail(str(e))

    def set_notify_callback(self, cb) -> None:
        """Set a callback for approval/notification messages (called with dict)."""
        self._notify_cb = cb

    async def startup(self) -> None:
        """Initialize DB, load schedules, run crash recovery."""
        await self._repo.initialize()

        def _make_callback(task_id: str):
            async def _run():
                task = await self._repo.get_task(task_id)
                if task:
                    await self.run_now(task_id)
            return _run

        await self._scheduler.start()
        await self._scheduler.load_from_db(self._repo, _make_callback)

        actions = await self._recovery.recover(self._repo)
        for action in actions:
            if action["action"] == "resume":
                asyncio.create_task(self.run_now(action["task_id"]))
            elif action["action"] == "ask_user" and self._notify_cb:
                await self._notify_cb({"type": "recovery", **action})

        logger.info("TaskManager startup complete")

    # ── Public API ────────────────────────────────────────────────────────────

    async def submit(
        self,
        goal: str,
        schedule_nl: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        dedup_key: Optional[str] = None,
    ) -> Task:
        """Create a Task from a goal string. Optionally schedule it."""
        # Deduplication
        if dedup_key:
            existing = await self._repo.list_tasks()
            for t in existing:
                if t.deduplication_key == dedup_key and not t.is_terminal():
                    logger.info("Dedup: returning existing task %s", t.id)
                    return t

        task = Task(title=goal, description=goal, priority=priority)
        if dedup_key:
            task.deduplication_key = dedup_key

        # Build steps via intent resolver + compound splitting
        steps = await self._build_steps(task, goal)
        task.steps = steps
        task.transition(TaskState.PLANNED)

        await self._repo.create_task(task)
        await self._repo.append_event(task.id, "TASK_CREATED", {"goal": goal})

        if schedule_nl:
            sched = self._nl_parser.parse(schedule_nl, task.id)
            await self._repo.save_schedule(sched)
            self._scheduler.add_schedule(sched, lambda: asyncio.create_task(self.run_now(task.id)))
            logger.info("Task %s scheduled: %s", task.id, schedule_nl)
        else:
            # Run immediately
            asyncio.create_task(self.run_now(task.id))

        return task

    async def run_now(self, task_id: str) -> dict:
        """Execute a task immediately."""
        task = await self._repo.get_task(task_id)
        if not task:
            return {"error": f"Task {task_id} not found"}
        if task.is_terminal():
            return {"error": f"Task {task_id} is already {task.state.value}"}

        task.transition(TaskState.RUNNING)
        await self._repo.update_task(task)
        await self._repo.append_event(task_id, "TASK_STARTED", {"started_at": time.time()})

        # Approval gate for risky steps
        risky = self._approval.filter_risky(task.steps)
        if risky:
            task.transition(TaskState.WAITING_FOR_APPROVAL)
            await self._repo.update_task(task)
            approval_id = await self._approval.request_approval(
                task_id, risky[0],
                notify_cb=self._notify_cb or (lambda x: asyncio.sleep(0)),
            )
            granted = await self._approval.wait_for_decision(approval_id, timeout=300.0)
            if not granted:
                task.transition(TaskState.CANCELLED)
                task.error = "Approval denied or timed out"
                await self._repo.update_task(task)
                return {"status": "cancelled", "reason": "approval denied"}
            task.transition(TaskState.RUNNING)
            await self._repo.update_task(task)

        executor = DAGExecutor(step_runner=self._step_runner, max_parallel=task.policy.max_parallel_steps)
        start = time.time()
        summary = await executor.execute(task, self._repo)
        duration = time.time() - start

        # Determine final state
        required_failed = [
            s for s in task.steps
            if s.state == StepState.FAILED and s.required
        ]
        if not required_failed:
            final_state = TaskState.COMPLETED if not task.failed_steps() else TaskState.PARTIALLY_COMPLETED
        elif len(task.completed_steps()) > 0:
            final_state = TaskState.PARTIALLY_COMPLETED
        else:
            final_state = TaskState.FAILED

        task.transition(final_state)
        task.context["last_run_duration"] = duration
        await self._repo.update_task(task)
        await self._repo.append_event(task_id, "TASK_COMPLETED", {"state": final_state.value, "duration": duration})
        logger.info("Task %s finished in %.1fs → %s", task_id, duration, final_state.value)
        return {**summary, "state": final_state.value, "duration_sec": round(duration, 2)}

    async def cancel(self, task_id: str) -> bool:
        task = await self._repo.get_task(task_id)
        if not task: return False
        task.transition(TaskState.CANCELLED)
        await self._repo.update_task(task)
        await self._repo.append_event(task_id, "TASK_CANCELLED", {})
        return True

    async def pause(self, task_id: str) -> bool:
        task = await self._repo.get_task(task_id)
        if not task or task.state != TaskState.RUNNING: return False
        task.transition(TaskState.PAUSED)
        await self._repo.update_task(task)
        return True

    async def resume(self, task_id: str) -> bool:
        task = await self._repo.get_task(task_id)
        if not task or task.state != TaskState.PAUSED: return False
        asyncio.create_task(self.run_now(task_id))
        return True

    async def skip_step(self, task_id: str, step_id: str) -> bool:
        task = await self._repo.get_task(task_id)
        if not task: return False
        for step in task.steps:
            if step.id == step_id:
                step.state = StepState.SKIPPED
                step.error = "Skipped by user"
                await self._repo.update_task(task)
                return True
        return False

    async def grant_approval(self, approval_id: str) -> None:
        self._approval.grant(approval_id)

    async def deny_approval(self, approval_id: str) -> None:
        self._approval.deny(approval_id)

    async def status(self, task_id: str) -> dict:
        task = await self._repo.get_task(task_id)
        if not task: return {"error": "not found"}
        return {
            "id": task.id,
            "title": task.title,
            "state": task.state.value,
            "progress": task.progress(),
            "steps": [
                {"name": s.name, "state": s.state.value, "result": str(s.result.output) if s.result else None}
                for s in task.steps
            ],
            "error": task.error,
        }

    async def list_tasks(self, filter: str = "active") -> list[dict]:
        state_map = {
            "active": None, "running": TaskState.RUNNING,
            "completed": TaskState.COMPLETED, "failed": TaskState.FAILED,
        }
        tasks = await self._repo.list_tasks(state=state_map.get(filter))
        return [{"id": t.id, "title": t.title, "state": t.state.value, "progress": t.progress()} for t in tasks]

    async def list_scheduled(self) -> list[dict]:
        scheds = await self._repo.list_schedules(enabled_only=True)
        return [{"id": s.id, "task_id": s.task_id, "recurrence": s.recurrence or s.raw_nl} for s in scheds]

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _build_steps(self, task: Task, goal: str) -> list[TaskStep]:
        """Decompose goal into TaskSteps using intent resolver + compound splitting."""
        import re
        from core.intent_resolver import intent_resolver
        compound_splitters = [
            r"\s+aur\s+uske\s+baad\s+", r"\s+or\s+uske\s+baad\s+", r"\s+phir\s+",
            r"\s+and\s+then\s+", r"\s+after\s+that\s+", r"\s+then\s+",
        ]
        regex = "|".join(compound_splitters)
        sub_goals = [s.strip() for s in re.split(regex, goal, flags=re.IGNORECASE) if s.strip()]
        steps = []
        for i, sg in enumerate(sub_goals):
            resolved = intent_resolver.resolve(sg)
            action = resolved.action if resolved.action != "chat" else "web_search"
            params = resolved.parameters if resolved.parameters else {"query": sg}
            prev_id = steps[i-1].id if i > 0 else None
            step = TaskStep(
                task_id=task.id,
                name=f"Step {i+1}: {sg[:40]}",
                action=action,
                parameters=params,
                dependencies=[prev_id] if prev_id else [],
            )
            steps.append(step)
        return steps
