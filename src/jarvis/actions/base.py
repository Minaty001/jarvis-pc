"""Base interfaces and data structures for JARVIS actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ActionResult:
    """Represents the execution outcome of an action."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        return self.message


class BaseAction:
    """Base class for all executable actions in JARVIS."""
    name: str = ""
    description: str = ""
    patterns: List[str] = []

    def execute(self, **kwargs: Any) -> ActionResult:
        """Execute the action with provided keyword arguments."""
        raise NotImplementedError("Subclasses must implement execute().")
