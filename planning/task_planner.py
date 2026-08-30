"""
Task Planner — Goal decomposition into executable plans.
Uses LLM for complex decomposition, heuristics for simple tasks.
"""

import json
import re
import time
from typing import Any, Optional

from config.logger import get_logger
from planning.plan_models import Plan, PlanStep

logger = get_logger("planning.task_planner")


class TaskPlanner:
    """Decomposes goals into dependency-aware execution plans."""

    def __init__(self):
        self._llm_gateway = None

    def inject_llm(self, llm_gateway):
        self._llm_gateway = llm_gateway

    async def create_plan(
        self,
        goal: str,
        available_tools: list[str] = None,
        world_state: Any = None,
        memory_context: str = None,
    ) -> Plan:
        """Create an execution plan for the given goal."""
        plan = Plan(goal=goal, status="planning")
        logger.info("Creating plan for: '%s'", goal[:60])

        # Try LLM-based decomposition for complex goals
        if self._llm_gateway and self._is_complex(goal):
            try:
                steps = await self._llm_decompose(goal, available_tools or [], world_state, memory_context)
                if steps:
                    for step_data in steps:
                        step = PlanStep.from_dict(step_data)
                        plan.add_step(step)
                    plan.status = "ready"
                    logger.info("LLM created plan with %d steps", len(plan.steps))
                    return plan
            except Exception as e:
                logger.warning("LLM decomposition failed: %s", e)

        # Fallback: single-step plan
        plan.add_step(PlanStep(
            description=goal,
            tool=None,
            parameters={"query": goal},
            risk_level=0,
        ))
        plan.status = "ready"
        return plan

    def _is_complex(self, goal: str) -> bool:
        """Determine if a goal requires multi-step decomposition."""
        indicators = [
            " and ", " then ", " after ", " before ", "also",
            "build", "test", "deploy", "debug", "fix", "create",
            "implement", "refactor", "analyze", "research", "compare",
            "setup", "configure", "optimize", "migrate", "review",
        ]
        goal_lower = goal.lower()
        return any(ind in goal_lower for ind in indicators)

    async def _llm_decompose(
        self,
        goal: str,
        available_tools: list[str],
        world_state: Any = None,
        memory_context: str = None,
    ) -> Optional[list[dict]]:
        """Use LLM to decompose a goal into steps."""
        tools_str = ", ".join(available_tools[:30]) if available_tools else "general tools"

        prompt = f"""Decompose this goal into concrete executable steps.

Goal: {goal}

Available tools: {tools_str}

Rules:
- Each step should be a single action
- Include tool name if a specific tool is needed
- Set risk_level: 0=read-only, 1=low, 2=moderate, 3=high, 4=critical
- List dependencies between steps
- Maximum 10 steps

Output a JSON array of steps:
[{{"id": "step-1", "description": "...", "tool": "tool_name_or_null", "parameters": {{}}, "dependencies": [], "risk_level": 0, "expected_result": "..."}}]"""

        if world_state:
            prompt += f"\n\nCurrent system state: {world_state.to_context_string()}"

        response = await self._llm_gateway.generate(
            prompt=prompt,
            task_type="reasoning",
            max_tokens=2000,
            temperature=0.2,
        )

        if response.text:
            return self._parse_llm_steps(response.text)
        return None

    def _parse_llm_steps(self, text: str) -> Optional[list[dict]]:
        """Parse JSON steps from LLM response."""
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if json_match:
            try:
                steps = json.loads(json_match.group())
                if isinstance(steps, list) and len(steps) > 0:
                    return steps
            except json.JSONDecodeError:
                pass
        return None


task_planner = TaskPlanner()
