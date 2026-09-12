"""Task and Multi-Action Planner for JARVIS.

Decomposes complex, multi-action natural language requests into structured execution steps,
matches action intents, and executes multi-task pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any, Dict, List, Optional

from .actions import ActionRegistry, ActionResult, BaseAction
from .brain import LLMBrain

logger = logging.getLogger("jarvis.planner")


@dataclass
class TaskStep:
    """A single atomic action step in a multi-action plan."""
    action: BaseAction
    params: Dict[str, Any]
    original_text: str

    def execute(self) -> ActionResult:
        """Execute this task step."""
        return self.action.execute(**self.params)


@dataclass
class ExecutionReport:
    """Complete summary of a multi-action execution sequence."""
    success: bool
    results: List[ActionResult]
    summary_message: str


class TaskPlanner:
    """Parses and orchestrates multi-action commands."""

    # Conjunctions and delimiters for splitting compound commands
    SPLIT_PATTERN = re.compile(
        r"\b(?:and\s+then|then|and|also|after\s+that|followed\s+by)\b|[,;]",
        re.IGNORECASE,
    )

    # Filler words to strip from clause beginnings
    FILLER_PREFIXES = re.compile(
        r"^(?:please\s+|jarvis\s+|can\s+you\s+|could\s+you\s+|would\s+you\s+|i\s+want\s+you\s+to\s+|hey\s+jarvis\s+)+",
        re.IGNORECASE,
    )

    def __init__(
        self,
        registry: Optional[ActionRegistry] = None,
        brain: Optional[LLMBrain] = None,
    ) -> None:
        self.registry = registry or ActionRegistry()
        self.brain = brain or LLMBrain()

    def split_clauses(self, command: str) -> List[str]:
        """Split a compound sentence into separate command clauses."""
        raw_parts = self.SPLIT_PATTERN.split(command)
        clauses: List[str] = []

        for part in raw_parts:
            cleaned = self.FILLER_PREFIXES.sub("", part.strip()).strip()
            if cleaned:
                clauses.append(cleaned)

        return clauses

    def parse_clause(self, clause: str) -> Optional[TaskStep]:
        """Match a single clause against registered actions."""
        clause_clean = clause.strip()
        
        for action in self.registry.all_actions():
            for pattern in action.patterns:
                match = re.search(pattern, clause_clean, re.IGNORECASE)
                if match:
                    # Extract named groups as parameters
                    params = match.groupdict()
                    # Also include non-empty values
                    clean_params = {k: v for k, v in params.items() if v is not None}
                    return TaskStep(action=action, params=clean_params, original_text=clause_clean)

        return None

    def plan(self, command: str) -> List[TaskStep]:
        """Decompose a full user command into an ordered list of TaskSteps."""
        clauses = self.split_clauses(command)
        steps: List[TaskStep] = []

        for clause in clauses:
            step = self.parse_clause(clause)
            if step:
                steps.append(step)
            else:
                logger.warning("Unrecognized subtask clause: '%s'", clause)

        return steps

    def execute_plan(self, steps: List[TaskStep]) -> ExecutionReport:
        """Execute a list of TaskSteps sequentially and generate combined response."""
        if not steps:
            return ExecutionReport(
                success=False,
                results=[],
                summary_message="I could not understand any specific tasks in that command.",
            )

        results: List[ActionResult] = []
        messages: List[str] = []
        all_success = True

        for idx, step in enumerate(steps, 1):
            logger.info("Executing step %d/%d: %s (%s)", idx, len(steps), step.action.name, step.params)
            res = step.execute()
            results.append(res)
            if res.success:
                messages.append(res.message)
            else:
                all_success = False
                messages.append(f"Failed: {res.message}")

        # Build natural spoken summary
        if len(messages) == 1:
            summary = messages[0]
        elif len(messages) == 2:
            summary = f"{messages[0]} and {messages[1]}"
        else:
            summary = ", ".join(messages[:-1]) + f", and {messages[-1]}"

        return ExecutionReport(success=all_success, results=results, summary_message=summary)

    def process(self, command: str) -> ExecutionReport:
        """Parse and execute a user command in one call, falling back to LLM brain if unhandled."""
        steps = self.plan(command)
        if steps:
            return self.execute_plan(steps)

        # Fallback to conversational LLM brain for general questions & chat
        logger.info("No system action matched; routing to Conversational LLM Brain...")
        answer = self.brain.ask(command)
        return ExecutionReport(
            success=True,
            results=[ActionResult(success=True, message=answer, data={"source": "llm_brain"})],
            summary_message=answer,
        )
