import logging
from typing import Any, Dict, Optional
from jarvis.cognitive.context import ExecutionContext
from jarvis.tools.executor import ToolExecutor
from jarvis.tasks.models import TaskPlan, TaskStep, StepStatus
from jarvis.tasks.lifecycle import transition_step

logger = logging.getLogger(__name__)


class TaskManager:
    """TaskManager orchestrates execution of TaskPlan steps through ToolExecutor."""

    def __init__(self, executor: ToolExecutor) -> None:
        self.executor = executor

    async def execute_step(
        self,
        step: TaskStep,
        context: ExecutionContext,
        confirmed: bool = False,
    ) -> Any:
        """Executes a single task step via the ToolExecutor single execution gate."""
        transition_step(step, StepStatus.RUNNING)
        try:
            result = await self.executor.execute(
                step.tool, context=context, confirmed=confirmed, **step.arguments
            )
            transition_step(step, StepStatus.COMPLETED, result=result)
            return result
        except Exception as exc:
            err_msg = str(exc)
            transition_step(step, StepStatus.FAILED, error=err_msg)
            raise

    async def execute_plan(
        self,
        plan: TaskPlan,
        context: ExecutionContext,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        """Executes all steps in a TaskPlan sequentially."""
        results: Dict[str, Any] = {}
        for step in plan.steps:
            try:
                result = await self.execute_step(step, context=context, confirmed=confirmed)
                results[step.id] = result
            except Exception as exc:
                logger.error(f"Step '{step.id}' failed in plan '{plan.id}': {exc}")
                break
        return results
