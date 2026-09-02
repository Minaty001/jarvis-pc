import logging
from typing import Any, Optional
from jarvis.tasks.models import TaskStep, StepStatus

logger = logging.getLogger(__name__)


def transition_step(
    step: TaskStep,
    target_status: StepStatus,
    result: Optional[Any] = None,
    error: Optional[str] = None,
) -> None:
    """Transitions a TaskStep to target_status and sets result/error accordingly."""
    step.status = target_status
    if target_status == StepStatus.COMPLETED:
        step.result = result
        step.error = None
    elif target_status == StepStatus.FAILED:
        step.error = error
        if error:
            logger.error(f"TaskStep '{step.id}' failed: {error}")
