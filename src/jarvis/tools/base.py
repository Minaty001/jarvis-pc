from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, FrozenSet
from jarvis.tools.policy import RiskLevel


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    risk: RiskLevel
    capabilities: FrozenSet[str] = frozenset()
    handler: Callable[..., Any] | None = None

    @property
    def risk_level(self) -> RiskLevel:
        return self.risk