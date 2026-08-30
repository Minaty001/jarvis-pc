"""
Task State — Task lifecycle management.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from planning.plan_models import Plan


class TaskStatus:
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING = "waiting"
    BLOCKED = "blocked"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    id: str = field(default_factory=lambda: f"task-{str(uuid.uuid4())[:8]}")
    goal: str = ""
    status: str = TaskStatus.PENDING
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    deadline: Optional[float] = None
    plan: Optional[Plan] = None
    state: dict = field(default_factory=dict)
    checkpoint: dict = field(default_factory=dict)
    memory_refs: list = field(default_factory=list)
    traces: list = field(default_factory=list)
    result: Optional[dict] = None
    error: Optional[str] = None

    def update_status(self, status: str) -> None:
        self.status = status
        self.updated_at = time.time()

    def add_trace(self, trace: dict) -> None:
        self.traces.append({**trace, "timestamp": time.time()})
        if len(self.traces) > 100:
            self.traces = self.traces[-100:]

    def save_checkpoint(self, data: dict) -> None:
        self.checkpoint.update(data)
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "progress": self.plan.progress() if self.plan else 0.0,
            "plan_summary": f"{self.plan.completed_count()}/{len(self.plan.steps)} steps" if self.plan else "no plan",
            "error": self.error,
        }


class TaskStore:
    """In-memory task store with persistence support."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def create(self, goal: str, priority: int = 0) -> Task:
        task = Task(goal=goal, priority=priority)
        self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_active(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)]

    def list_all(self) -> list[Task]:
        return list(self._tasks.values())

    def get_by_status(self, status: str) -> list[Task]:
        """Get all tasks with a specific status."""
        return [t for t in self._tasks.values() if t.status == status]

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task and task.status not in (TaskStatus.COMPLETED,):
            task.update_status(TaskStatus.CANCELLED)
            return True
        return False


task_store = TaskStore()
