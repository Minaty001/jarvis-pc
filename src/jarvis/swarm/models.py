"""Data models and enums for Autonomous Swarm Orchestration in JARVIS PC."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any, Dict, List, Optional


class WorkerRole(str, Enum):
    """Specialized roles for swarm subagents."""
    RESEARCHER = "researcher"
    CODER = "coder"
    SYSTEM = "system"
    WRITER = "writer"
    GENERAL = "general"


class TaskStatus(str, Enum):
    """Lifecycle status of a swarm task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SwarmLogEntry:
    """Individual timestamped execution log for a worker."""
    timestamp: str
    message: str
    level: str = "INFO"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SwarmTask:
    """Represents a delegated background task for a sub-agent worker."""
    id: str = field(default_factory=lambda: f"swarm-{uuid.uuid4().hex[:8]}")
    parent_goal: str = ""
    role: WorkerRole = WorkerRole.GENERAL
    instruction: str = ""
    name: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    error: Optional[str] = None
    progress_percent: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    logs: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["role"] = self.role.value if isinstance(self.role, WorkerRole) else str(self.role)
        data["status"] = self.status.value if isinstance(self.status, TaskStatus) else str(self.status)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SwarmTask:
        role_val = data.get("role", "general")
        status_val = data.get("status", "pending")
        return cls(
            id=data.get("id", f"swarm-{uuid.uuid4().hex[:8]}"),
            parent_goal=data.get("parent_goal", ""),
            role=WorkerRole(role_val) if role_val in [r.value for r in WorkerRole] else WorkerRole.GENERAL,
            instruction=data.get("instruction", ""),
            name=data.get("name", ""),
            status=TaskStatus(status_val) if status_val in [s.value for s in TaskStatus] else TaskStatus.PENDING,
            result=data.get("result", ""),
            error=data.get("error"),
            progress_percent=data.get("progress_percent", 0),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            logs=data.get("logs", []),
            metadata=data.get("metadata", {}),
        )
