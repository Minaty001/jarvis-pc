from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, FrozenSet
from jarvis.tools.policy import RiskLevel


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    risk: RiskLevel
    capabilities: FrozenSet[str]
    handler: Callable[..., Any]

    def __init__(
        self,
        name: str,
        risk: RiskLevel | None = None,
        capabilities: FrozenSet[str] | Callable[..., Any] | None = None,
        handler: Callable[..., Any] | None = None,
        risk_level: RiskLevel | None = None,
    ) -> None:
        r = risk if risk is not None else risk_level
        if r is None:
            raise TypeError("ToolDefinition requires 'risk' or 'risk_level'")

        if callable(capabilities) and handler is None:
            actual_handler = capabilities
            actual_caps = frozenset()
        else:
            actual_handler = handler
            actual_caps = capabilities if capabilities is not None else frozenset()

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "risk", r)
        object.__setattr__(self, "capabilities", frozenset(actual_caps))
        object.__setattr__(self, "handler", actual_handler)

    @property
    def risk_level(self) -> RiskLevel:
        return self.risk
