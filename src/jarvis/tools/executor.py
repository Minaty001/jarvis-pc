from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable, Dict, Optional

from jarvis.cognitive.context import ExecutionContext
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel
from jarvis.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolDenied(Exception):
    """Raised when execution of a tool is denied by policy."""
    pass


class ConfirmationRequired(Exception):
    """Raised when execution of a tool requires explicit user confirmation."""
    pass


class ToolExecutor:
    """Single execution gate for all tools in the system enforcing risk policies."""

    def __init__(self, registry: Optional[ToolRegistry] = None) -> None:
        self.registry: ToolRegistry = registry if registry is not None else ToolRegistry()

    def register(self, tool: ToolDefinition) -> None:
        self.registry.register(tool)

    def get_tool(self, name: str) -> ToolDefinition:
        tool = self.registry.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' is not registered.")
        return tool

    async def execute(
        self,
        tool_name: Optional[str] = None,
        *args: Any,
        context: Optional[ExecutionContext] = None,
        confirmed: bool = False,
        arguments: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        target_name = tool_name or name
        if target_name is None and args:
            target_name = args[0]
            args = args[1:]

        if target_name is None:
            raise ValueError("Tool name must be specified.")

        tool = self.get_tool(target_name)

        if tool.risk in (RiskLevel.FORBIDDEN, RiskLevel.PRIVILEGED):
            raise ToolDenied(
                f"Execution of tool '{target_name}' is denied due to risk level '{tool.risk.value}'."
            )

        if tool.risk == RiskLevel.CONFIRM and not confirmed:
            raise ConfirmationRequired(
                f"Execution of tool '{target_name}' requires explicit user confirmation."
            )

        logger.info(
            "Executing tool=%s risk=%s request_id=%s",
            tool.name,
            tool.risk.value if hasattr(tool.risk, "value") else str(tool.risk),
            context.request_id if context else "none",
        )

        handler_kwargs: Dict[str, Any] = {}
        if arguments:
            handler_kwargs.update(arguments)
        handler_kwargs.update(kwargs)

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
