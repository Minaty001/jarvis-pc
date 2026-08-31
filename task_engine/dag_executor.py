# task_engine/dag_executor.py
"""DAG Executor — runs Task steps with parallel execution and dependency awareness."""
from __future__ import annotations
import asyncio, time
from typing import Awaitable, Callable, Optional
from config.logger import get_logger
from task_engine.models import Task, TaskStep, StepState, ActionResult, FailureClass

logger = get_logger("task_engine.dag_executor")

StepRunner = Callable[[str, dict], Awaitable[ActionResult]]


class DAGExecutor:
    """Executes a Task's steps respecting DAG dependencies and concurrency limits."""

    def __init__(
        self,
        step_runner: StepRunner,
        max_parallel: int = 4,
    ):
        self._run = step_runner
        self.max_parallel = max_parallel

    async def execute(self, task: Task, repo) -> dict:
        """Run all steps in dependency order. Returns summary dict."""
        semaphore = asyncio.Semaphore(self.max_parallel)
        step_map = {s.id: s for s in task.steps}
        completed_ids: set[str] = set()
        failed_ids: set[str] = set()  # required failures
        pending = list(task.steps)
        results = []

        # Restore already-completed steps from checkpoints
        for step in task.steps:
            if step.state == StepState.COMPLETED:
                completed_ids.add(step.id)
                logger.info("Skipping already-completed step %s (checkpoint)", step.id)

        while pending:
            ready = []
            for step in list(pending):
                if step.id in completed_ids:
                    pending.remove(step)
                    continue
                # Check if any required dependency failed
                blocked = any(d in failed_ids for d in step.dependencies)
                if blocked:
                    step.state = StepState.SKIPPED
                    step.error = "Dependency failed"
                    pending.remove(step)
                    results.append({"step_id": step.id, "state": "skipped", "reason": "dependency failed"})
                    logger.info("Skipping step %s — dependency failed", step.id)
                    await repo.append_event(task.id, "STEP_SKIPPED", {"step_id": step.id})
                    continue
                deps_met = all(
                    step_map[d].state == StepState.COMPLETED
                    for d in step.dependencies
                    if d in step_map
                )
                if deps_met:
                    ready.append(step)
                    pending.remove(step)

            if not ready:
                if pending:
                    logger.warning("DAG stalled — %d steps remain with unresolvable deps", len(pending))
                    for step in pending:
                        step.state = StepState.SKIPPED
                        step.error = "DAG stalled"
                        results.append({"step_id": step.id, "state": "skipped", "reason": "stalled"})
                break

            async def run_step(step: TaskStep):
                async with semaphore:
                    if step.state == StepState.COMPLETED:
                        return
                    step.mark_running()
                    await repo.append_event(task.id, "STEP_STARTED", {"step_id": step.id, "action": step.action})
                    logger.info("Executing step %s: %s", step.id, step.action)
                    try:
                        for attempt in range(step.max_attempts):
                            result = await self._run(step.action, step.parameters)
                            if result.success:
                                step.mark_completed(result)
                                completed_ids.add(step.id)
                                await repo.save_checkpoint(task.id, step.id, {"output": str(result.output)})
                                await repo.append_event(task.id, "STEP_COMPLETED", {"step_id": step.id})
                                results.append({"step_id": step.id, "state": "completed", "output": result.output})
                                logger.info("Step %s completed", step.id)
                                return
                            else:
                                if not result.retryable or attempt == step.max_attempts - 1:
                                    break
                                wait = min(1.0 * (2 ** attempt), 30.0)
                                logger.info("Step %s retry %d in %.1fs", step.id, attempt + 2, wait)
                                await asyncio.sleep(wait)

                        step.mark_failed(result.error_msg if result else "unknown", result)
                        await repo.append_event(task.id, "STEP_FAILED", {"step_id": step.id, "error": step.error})
                        results.append({"step_id": step.id, "state": "failed", "error": step.error})
                        if step.required:
                            failed_ids.add(step.id)
                        logger.warning("Step %s failed: %s", step.id, step.error)
                    except Exception as exc:
                        step.mark_failed(str(exc))
                        failed_ids.add(step.id)
                        results.append({"step_id": step.id, "state": "failed", "error": str(exc)})
                        await repo.append_event(task.id, "STEP_FAILED", {"step_id": step.id, "error": str(exc)})

            await asyncio.gather(*[run_step(s) for s in ready])

        done = sum(1 for s in task.steps if s.state == StepState.COMPLETED)
        failed = sum(1 for s in task.steps if s.state == StepState.FAILED)
        skipped = sum(1 for s in task.steps if s.state == StepState.SKIPPED)
        return {"completed": done, "failed": failed, "skipped": skipped, "results": results}
