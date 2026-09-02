from __future__ import annotations

from typing import Dict, List, Optional
from jarvis.tools.base import ToolDefinition


class ToolRegistry:
    """Canonical registry for tools in JARVIS."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def list(self) -> List[ToolDefinition]:
        return list(self._tools.values())
