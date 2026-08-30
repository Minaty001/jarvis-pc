"""
Tool Executor — Executes tools through the security policy with verification and audit.
Central dispatch point for all tool calls.
"""

import asyncio
import time
from typing import Any, Optional

from config.logger import get_logger
from tools.registry import ToolDef, tool_registry
from tools.security import security_policy

logger = get_logger("tools.executor")


class ToolExecutor:
    """Executes tools through policy gates with logging and error handling."""

    def __init__(self, require_confirmation: bool = False):
        self.require_confirmation = require_confirmation
        self._pending_confirmations: dict[str, dict] = {}

    async def execute(
        self,
        tool_name: str,
        args: dict,
        user_context: Optional[dict] = None,
    ) -> dict:
        """
        Execute a tool by name with args.
        Returns {"success": bool, "result": Any, "error": str}.
        """
        tool = tool_registry.get(tool_name)
        if not tool:
            return {"success": False, "result": None, "error": f"Tool '{tool_name}' not found"}

        # Rate limit check
        can_call, reason = tool_registry.can_call(tool_name)
        if not can_call:
            return {"success": False, "result": None, "error": reason}

        # Security policy check
        allowed, policy_msg, _ = security_policy.evaluate(tool, args, user_context)
        if not allowed:
            return {"success": False, "result": None, "error": f"Security: {policy_msg}"}

        # Execute
        start = time.time()
        try:
            if asyncio.iscoroutinefunction(tool.handler):
                result = await tool.handler(**args)
            else:
                result = tool.handler(**args)

            duration = time.time() - start
            tool_registry.record_call(tool_name, True, duration)
            logger.info("Tool '%s' executed in %.2fs", tool_name, duration)
            return {"success": True, "result": result, "error": ""}

        except Exception as e:
            duration = time.time() - start
            tool_registry.record_call(tool_name, False, duration)
            logger.error("Tool '%s' failed: %s", tool_name, e)
            return {"success": False, "result": None, "error": str(e)}

    def create_tool_def(
        self,
        name: str,
        description: str,
        handler: Any,
        category: Any = None,
        risk_level: Any = None,
        **kwargs,
    ) -> ToolDef:
        """Helper to create and register a ToolDef."""
        from tools.registry import ToolCategory, RiskLevel

        tool = ToolDef(
            name=name,
            description=description,
            category=category or ToolCategory.CUSTOM,
            risk_level=risk_level or RiskLevel.LOW,
            handler=handler,
            **kwargs,
        )
        tool_registry.register(tool)
        return tool


tool_executor = ToolExecutor()
