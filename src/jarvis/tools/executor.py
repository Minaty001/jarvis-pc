from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable, Dict, Optional

from jarvis.cognitive.context import ExecutionContext
from jarvis.tools.audit import AuditLogger
from jarvis.tools.base import ToolDefinition
from jarvis.tools.confirmation import verify_confirmation_token
from jarvis.tools.policy import RiskLevel
from jarvis.tools.rate_limit import RateLimiter
from jarvis.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolDenied(Exception):
    """Raised when execution of a tool is denied by policy."""
    pass


class ConfirmationRequired(Exception):
    """Raised when execution of a tool requires explicit user confirmation."""
    pass


class ToolExecutor:
    """Single execution gate for all tools in the system enforcing risk policies, rate limits, and audit logging."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        rate_limiter: Optional[RateLimiter] = None,
        audit_logger: Optional[AuditLogger] = None,
        confirmation_secret: Optional[str] = None,
    ) -> None:
        self.registry: ToolRegistry = registry if registry is not None else ToolRegistry()
        self.rate_limiter: RateLimiter = rate_limiter if rate_limiter is not None else RateLimiter()
        self.audit_logger: AuditLogger = audit_logger if audit_logger is not None else AuditLogger()
        self._confirmation_secret: Optional[str] = confirmation_secret

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
        context: ExecutionContext,
        confirmation_token: Optional[str] = None,
        secret: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        if context is None or not isinstance(context, ExecutionContext):
            raise TypeError("ExecutionContext is mandatory for tool execution.")

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

        if tool.capabilities:
            if not (tool.capabilities <= context.permissions):
                raise ToolDenied(
                    f"Insufficient capabilities for tool '{target_name}'. Required: {set(tool.capabilities)}, provided: {set(context.permissions)}"
                )

        clean_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in ("confirmed", "confirmation_token", "secret")
        }
        verify_args = arguments if arguments is not None else (clean_kwargs if clean_kwargs else None)

        if tool.risk == RiskLevel.CONFIRM:
            if not confirmation_token:
                raise ConfirmationRequired(
                    f"Execution of tool '{target_name}' requires explicit user confirmation."
                )
            session_id = context.session_id
            confirmation_secret = secret or self._confirmation_secret
            if not confirmation_secret:
                raise ToolDenied("Confirmation secret is not configured. Cannot verify confirmation tokens.")
            if not verify_confirmation_token(
                target_name, verify_args, session_id, confirmation_secret, confirmation_token
            ):
                raise ToolDenied("Invalid, expired, or tampered confirmation token")

        self.rate_limiter.check(target_name)

        logger.info(
            "Executing tool=%s risk=%s request_id=%s",
            tool.name,
            tool.risk.value if hasattr(tool.risk, "value") else str(tool.risk),
            context.request_id,
        )

        handler_kwargs: Dict[str, Any] = {}
        if arguments:
            handler_kwargs.update(arguments)
        handler_kwargs.update(clean_kwargs)

        request_id = context.request_id
        risk_str = tool.risk.value if hasattr(tool.risk, "value") else str(tool.risk)

        try:
            if asyncio.iscoroutinefunction(tool.handler) or inspect.iscoroutinefunction(tool.handler):
                res = await tool.handler(*args, **handler_kwargs)
            else:
                res = await asyncio.to_thread(tool.handler, *args, **handler_kwargs)

            self.audit_logger.log_execution(
                request_id=request_id,
                tool_name=tool.name,
                risk=risk_str,
                status="success",
                arguments=handler_kwargs,
            )
            return res
        except Exception as exc:
            self.audit_logger.log_execution(
                request_id=request_id,
                tool_name=tool.name,
                risk=risk_str,
                status="failed",
                arguments=handler_kwargs,
            )
            raise

