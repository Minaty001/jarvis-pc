"""
World State — Structured, versioned representation of PC state.
Aggregates signals from perception layer into a queryable state object.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class WorldState:
    """Current state of the world as perceived by Jarvis."""
    version: int = 0
    timestamp: float = field(default_factory=time.time)

    # User Context
    current_user_intent: str = ""
    current_goal: str = ""
    active_task_id: str = ""

    # PC State
    active_application: str = ""
    active_window_title: str = ""
    running_processes: list = field(default_factory=list)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    network_connected: bool = True
    battery_percent: Optional[float] = None
    battery_plugged: Optional[bool] = None

    # Task Context
    task_status: str = "idle"  # idle/planning/executing/verifying/blocked
    recent_actions: list = field(default_factory=list)
    recent_errors: list = field(default_factory=list)
    active_files: list = field(default_factory=list)

    # Workflow
    workflow_state: str = "idle"  # idle/researching/coding/debugging/writing/browsing/communicating
    workflow_confidence: float = 0.0
    estimated_progress: float = 0.0
    blockers: list = field(default_factory=list)
    last_workflow_transition: float = 0.0

    def update(self, **kwargs) -> None:
        """Incrementally update state fields."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.version += 1
        self.timestamp = time.time()

    def add_recent_action(self, action: dict) -> None:
        """Add an action to recent history, keeping last 20."""
        self.recent_actions.append({**action, "timestamp": time.time()})
        if len(self.recent_actions) > 20:
            self.recent_actions = self.recent_actions[-20:]

    def add_error(self, error: str) -> None:
        """Add an error to recent history, keeping last 10."""
        self.recent_errors.append({"error": error, "timestamp": time.time()})
        if len(self.recent_errors) > 10:
            self.recent_errors = self.recent_errors[-10:]

    def diff(self, other: "WorldState") -> dict:
        """Compare two states and return changed fields."""
        changes = {}
        for f in self.__dataclass_fields__:
            v1 = getattr(self, f)
            v2 = getattr(other, f)
            if v1 != v2:
                changes[f] = {"old": v1, "new": v2}
        return changes

    def to_context_string(self) -> str:
        """Compact string for LLM context injection."""
        parts = [
            f"System: CPU {self.cpu_percent:.0f}%, RAM {self.memory_percent:.0f}%, Disk {self.disk_percent:.0f}%",
            f"App: {self.active_application or 'unknown'}",
            f"Workflow: {self.workflow_state} ({self.workflow_confidence:.0%})",
            f"Task: {self.task_status}",
        ]
        if self.recent_errors:
            parts.append(f"Recent errors: {len(self.recent_errors)}")
        if self.blockers:
            parts.append(f"Blockers: {', '.join(self.blockers[:3])}")
        return " | ".join(parts)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "current_user_intent": self.current_user_intent,
            "current_goal": self.current_goal,
            "active_task_id": self.active_task_id,
            "active_application": self.active_application,
            "active_window_title": self.active_window_title,
            "running_processes": self.running_processes[:10],
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "disk_percent": self.disk_percent,
            "network_connected": self.network_connected,
            "battery_percent": self.battery_percent,
            "task_status": self.task_status,
            "recent_actions": self.recent_actions[-5:],
            "recent_errors": self.recent_errors[-3:],
            "workflow_state": self.workflow_state,
            "workflow_confidence": self.workflow_confidence,
            "estimated_progress": self.estimated_progress,
            "blockers": self.blockers,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorldState":
        """Deserialize from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


world_state = WorldState()
