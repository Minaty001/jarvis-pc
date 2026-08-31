"""
Plan Validator — Enforces Pydantic schema validation, tool registration checks,
and DAG cycle detection on all execution plans before running.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

from config.logger import get_logger
from tools.registry import tool_registry

logger = get_logger("planning.validator")


class ValidatedPlanStep(BaseModel):
    id: str = Field(..., description="Unique step identifier")
    description: str = Field("", description="Step description")
    tool: Optional[str] = Field(None, description="Registered tool name")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool execution parameters")
    dependencies: list[str] = Field(default_factory=list, description="IDs of preceding steps")
    risk_level: int = Field(0, description="Risk level (overridden deterministically by policy)")

    @field_validator("tool")
    def check_tool_exists(cls, v):
        if v is not None:
            tool_def = tool_registry.get(v)
            if tool_def is None and v not in ("chat", "reason"):
                logger.warning("Plan step specifies unregistered tool: %s", v)
        return v


class ValidatedPlan(BaseModel):
    goal: str = Field(..., description="Target goal string")
    steps: list[ValidatedPlanStep] = Field(default_factory=list, description="Ordered plan steps")

    @field_validator("steps")
    def check_dag_cycles(cls, steps):
        # Check for circular dependencies
        step_ids = {s.id for s in steps}
        graph = {s.id: set(s.dependencies) for s in steps}

        # Validate dependency references exist
        for s in steps:
            for dep in s.dependencies:
                if dep not in step_ids:
                    raise ValueError(f"Step '{s.id}' references non-existent dependency '{dep}'")

        # Cycle detection using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for node in step_ids:
            if node not in visited:
                if has_cycle(node):
                    raise ValueError("Plan contains circular dependency cycle")

        return steps


class PlanValidator:
    """Validates raw dict plans against Pydantic schema and DAG rules."""

    def validate(self, raw_plan: dict) -> tuple[bool, Optional[ValidatedPlan], str]:
        try:
            plan = ValidatedPlan.model_validate(raw_plan)
            return True, plan, "Plan is valid"
        except Exception as e:
            logger.error("Plan validation failed: %s", e)
            return False, None, str(e)


plan_validator = PlanValidator()
