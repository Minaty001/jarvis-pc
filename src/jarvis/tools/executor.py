import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from jarvis.tools.policy import RiskLevel


class ToolDenied(Exception):
    """Raised when execution of a tool is denied by policy."""
    pass


class ConfirmationRequired(Exception):
    """Raised when execution of a tool requires explicit user confirmation."""
    pass


@dataclass
class ToolDefinition:
    name: str
    risk_level: RiskLevel
    handler: Callable[..., Any]
    description: str = ""


class ToolExecutor:
    """Single execution gate for all tools in the system enforcing risk policies."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        return self._tools[name]

    async def execute(self, name: str, *args: Any, confirmed: bool = False, **kwargs: Any) -> Any:
        tool = self.get_tool(name)

        if tool.risk_level in (RiskLevel.FORBIDDEN, RiskLevel.PRIVILEGED):
            raise ToolDenied(
                f"Execution of tool '{name}' is denied due to risk level '{tool.risk_level.value}'."
            )

        if tool.risk_level == RiskLevel.CONFIRM and not confirmed:
            raise ConfirmationRequired(
                f"Execution of tool '{name}' requires explicit user confirmation."
            )

        # Build kwargs for the handler
        handler_kwargs = dict(kwargs)
        try:
            sig = inspect.signature(tool.handler)
            has_var_kw = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )
            if "confirmed" in sig.parameters or has_var_kw:
                handler_kwargs["confirmed"] = confirmed
        except (ValueError, TypeError):
            pass

        if asyncio.iscoroutinefunction(tool.handler) or inspect.iscoroutinefunction(tool.handler):
            return await tool.handler(*args, **handler_kwargs)

        res = tool.handler(*args, **handler_kwargs)
        if inspect.isawaitable(res):
            return await res
        return res
