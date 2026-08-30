"""
Task Planner — Multi-step action planning.
Decomposes complex intents into executable action sequences.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from config.logger import get_logger
from core.intent_resolver import Intent, intent_resolver

logger = get_logger("core.planner")


@dataclass
class ActionStep:
    id: str
    tool: str
    parameters: dict[str, Any] = field(default_factory=dict)
    depends_on: Optional[str] = None


@dataclass
class ExecutionPlan:
    request_id: str
    utterance: str
    steps: list[ActionStep] = field(default_factory=list)
    session_id: str = "default"


class TaskPlanner:
    """Plan and decompose user utterances into action steps."""

    def plan(self, text: str, request_id: str = "req-1", session_id: str = "default") -> ExecutionPlan:
        intent = intent_resolver.resolve(text)
        plan = ExecutionPlan(request_id=request_id, utterance=text, session_id=session_id)

        if intent.action == "chat":
            plan.steps.append(ActionStep(
                id=f"{request_id}-chat",
                tool="chat",
                parameters={"query": text},
            ))
        else:
            plan.steps.append(ActionStep(
                id=f"{request_id}-cmd",
                tool=intent.action,
                parameters=intent.parameters,
            ))

        logger.info("Planned %d step(s) for: '%s'", len(plan.steps), text[:50])
        return plan


task_planner = TaskPlanner()
