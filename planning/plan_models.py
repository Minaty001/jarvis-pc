"""
Plan Models — Structured task plan dataclasses.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PlanStep:
    id: str = field(default_factory=lambda: f"step-{str(uuid.uuid4())[:6]}")
    description: str = ""
    tool: Optional[str] = None
    parameters: dict = field(default_factory=dict)
    dependencies: list = field(default_factory=list)
    risk_level: int = 0
    expected_result: str = ""
    status: str = "pending"  # pending/running/completed/failed/skipped/blocked
    attempts: int = 0
    max_attempts: int = 3
    output: str = ""
    error: str = ""
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "tool": self.tool,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "risk_level": self.risk_level,
            "expected_result": self.expected_result,
            "status": self.status,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "output": self.output,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlanStep":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Plan:
    id: str = field(default_factory=lambda: f"plan-{str(uuid.uuid4())[:6]}")
    goal: str = ""
    steps: list = field(default_factory=list)
    status: str = "planning"  # planning/executing/completed/failed/cancelled
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    checkpoint: dict = field(default_factory=dict)

    def add_step(self, step: PlanStep) -> None:
        self.steps.append(step)
        self.updated_at = time.time()

    def get_step(self, step_id: str) -> Optional[PlanStep]:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def dependencies_met(self, step: PlanStep) -> bool:
        """Check if all dependencies of a step are completed."""
        for dep_id in step.dependencies:
            dep = self.get_step(dep_id)
            if dep is None or dep.status != "completed":
                return False
        return True

    def completed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "completed")

    def failed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "failed")

    def progress(self) -> float:
        if not self.steps:
            return 0.0
        return self.completed_count() / len(self.steps)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "progress": self.progress(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        steps = [PlanStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            id=data.get("id", f"plan-{str(uuid.uuid4())[:6]}"),
            goal=data.get("goal", ""),
            steps=steps,
            status=data.get("status", "planning"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )
