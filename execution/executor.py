"""
Executor — Tool dispatch with policy checks and verification.
"""

import asyncio
import time
from typing import Any, Optional

from config.logger import get_logger
from execution.critic import critic, VerificationStatus
from execution.retry_manager import retry_manager

logger = get_logger("execution.executor")


class Executor:
    """Execute tool calls with policy checks, retries, and verification."""

    def __init__(self):
        self._tool_executor = None
        self._permission_engine = None
        self._llm_gateway = None

    def inject_dependencies(self, tool_executor=None, permission_engine=None, llm_gateway=None):
        self._tool_executor = tool_executor
        self._permission_engine = permission_engine
        self._llm_gateway = llm_gateway
        critic.inject_dependencies(llm_gateway=llm_gateway)

    async def execute_step(
        self,
        step_id: str,
        description: str,
        tool: Optional[str],
        parameters: dict,
        risk_level: int = 0,
        expected_result: str = "",
        max_retries: int = 2,
    ) -> dict:
        """Execute a single step with full lifecycle."""
        start_time = time.time()

        # Policy check
        if self._permission_engine and risk_level >= 3:
            approved = await self._permission_engine.request_approval(
                action=tool or "reason",
                target=description,
                risk_level=risk_level,
            )
            if not approved:
                return {
                    "step_id": step_id,
                    "status": "blocked",
                    "reason": "permission denied",
                    "duration_ms": (time.time() - start_time) * 1000,
                }

        # Execute with retry
        if tool and self._tool_executor:
            result = await retry_manager.execute_with_retry(
                self._execute_tool, tool, parameters, max_retries=max_retries
            )
        else:
            result = await retry_manager.execute_with_retry(
                self._execute_reasoning, description, parameters, max_retries=max_retries
            )

        # Verify
        verification = critic.evaluate_step(
            step_description=description,
            expected_result=expected_result,
            actual_result=result,
        )

        duration_ms = (time.time() - start_time) * 1000

        return {
            "step_id": step_id,
            "status": "success" if verification["status"] == VerificationStatus.SUCCESS else verification["status"].lower(),
            "tool": tool,
            "result": result.get("result", ""),
            "error": result.get("error"),
            "verification": verification,
            "duration_ms": round(duration_ms, 2),
            "retries": result.get("attempts", 1) - 1,
        }

    async def _execute_tool(self, tool: str, params: dict) -> dict:
        """Execute a tool call."""
        try:
            result = await self._tool_executor.execute(tool, **params)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_reasoning(self, description: str, params: dict) -> dict:
        """Execute a reasoning step via LLM."""
        if not self._llm_gateway:
            return {"success": False, "error": "No LLM available"}

        try:
            prompt = params.get("query", description)
            response = await self._llm_gateway.generate(
                prompt=prompt,
                task_type="reasoning",
                max_tokens=1000,
            )
            return {"success": True, "result": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}


executor = Executor()
