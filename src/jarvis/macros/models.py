"""Data models and schemas for workflow macros and action steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StepType(str, Enum):
    TOOL = "tool"
    COMMAND = "command"
    SPEAK = "speak"
    NOTIFY = "notify"
    PAUSE = "pause"
    OPEN_APP = "open_app"
    OPEN_URL = "open_url"
    MOUSE_CLICK = "mouse_click"
    MOUSE_MOVE = "mouse_move"
    TYPE_TEXT = "type_text"
    KEY_COMBO = "key_combo"
    FOCUS_WINDOW = "focus_window"
    WAIT_FOR_WINDOW = "wait_for_window"
    ASSERT_PROCESS = "assert_process"


@dataclass
class MacroStep:
    type: StepType
    target: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 30.0
    ignore_errors: bool = False
    retries: int = 0
    description: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MacroStep:
        raw_type = data.get("type", "command")
        step_type = StepType(raw_type) if isinstance(raw_type, str) else raw_type
        return cls(
            type=step_type,
            target=data.get("target", ""),
            args=data.get("args", {}),
            timeout=float(data.get("timeout", 30.0)),
            ignore_errors=bool(data.get("ignore_errors", False)),
            retries=int(data.get("retries", 0)),
            description=data.get("description", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "target": self.target,
            "args": self.args,
            "timeout": self.timeout,
            "ignore_errors": self.ignore_errors,
            "retries": self.retries,
            "description": self.description,
        }


@dataclass
class MacroDefinition:
    name: str
    description: str = ""
    triggers: List[str] = field(default_factory=list)
    steps: List[MacroStep] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    confirmation_required: bool = False
    enabled: bool = True
    created_at: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MacroDefinition:
        raw_steps = data.get("steps", [])
        steps = [MacroStep.from_dict(s) for s in raw_steps]
        return cls(
            name=data.get("name", "unnamed_macro"),
            description=data.get("description", ""),
            triggers=data.get("triggers", []),
            steps=steps,
            variables=data.get("variables", {}),
            confirmation_required=bool(data.get("confirmation_required", False)),
            enabled=bool(data.get("enabled", True)),
            created_at=int(data.get("created_at", 0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "triggers": self.triggers,
            "steps": [s.to_dict() for s in self.steps],
            "variables": self.variables,
            "confirmation_required": self.confirmation_required,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }
