"""
Critic / Verification Engine — Evaluates action results.
Classifies outcomes and triggers recovery on failure.
"""

import json
from typing import Any, Optional

from config.logger import get_logger

logger = get_logger("execution.critic")


class VerificationStatus:
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILURE = "FAILURE"
    BLOCKED = "BLOCKED"
    REQUIRES_USER = "REQUIRES_USER"
    UNKNOWN = "UNKNOWN"


class Critic:
    """Evaluates whether actions achieved their intended effect."""

    def __init__(self):
        self._llm_gateway = None
        self._failure_memory = None

    def inject_dependencies(self, llm_gateway=None, failure_memory=None):
        self._llm_gateway = llm_gateway
        self._failure_memory = failure_memory

    def evaluate_step(
        self,
        step_description: str,
        expected_result: str,
        actual_result: dict,
    ) -> dict:
        """Evaluate a single step's result (deterministic)."""
        success = actual_result.get("success", False)
        output = actual_result.get("result", "")
        error = actual_result.get("error", "")

        if success:
            return {
                "status": VerificationStatus.SUCCESS,
                "reason": "Tool returned success",
                "should_retry": False,
            }

        if error:
            retryable = self._is_retryable_error(error)
            return {
                "status": VerificationStatus.FAILURE,
                "reason": error,
                "should_retry": retryable,
                "error_type": self._classify_error(error),
            }

        return {
            "status": VerificationStatus.FAILURE,
            "reason": "Tool returned failure without error message",
            "should_retry": False,
        }

    async def evaluate_with_llm(
        self,
        step_description: str,
        expected_result: str,
        actual_result: str,
    ) -> dict:
        """Use LLM for nuanced verification of complex results."""
        if not self._llm_gateway:
            return self.evaluate_step(step_description, expected_result, {"success": False, "result": actual_result})

        try:
            prompt = f"""Evaluate if this action achieved its goal.

Action: {step_description}
Expected: {expected_result}
Actual: {actual_result[:500]}

Classify as: SUCCESS, PARTIAL_SUCCESS, FAILURE, BLOCKED, REQUIRES_USER
Output JSON: {{"status": "...", "reason": "...", "should_retry": false}}"""

            response = await self._llm_gateway.generate(
                prompt=prompt,
                task_type="reasoning",
                max_tokens=200,
                temperature=0.1,
            )

            if response.text:
                parsed = json.loads(response.text)
                return {
                    "status": parsed.get("status", VerificationStatus.FAILURE),
                    "reason": parsed.get("reason", "LLM evaluation"),
                    "should_retry": parsed.get("should_retry", False),
                }
        except Exception as e:
            logger.warning("LLM verification failed: %s", e)

        return {"status": VerificationStatus.UNKNOWN, "reason": "Verification inconclusive", "should_retry": False}

    def _is_retryable_error(self, error: str) -> bool:
        """Determine if an error is retryable."""
        retryable_patterns = [
            "timeout", "timed out", "connection", "network",
            "temporary", "busy", "unavailable", "rate limit",
        ]
        error_lower = error.lower()
        return any(p in error_lower for p in retryable_patterns)

    def _classify_error(self, error: str) -> str:
        """Classify error type for recovery strategy."""
        error_lower = error.lower()
        if "not found" in error_lower or "no such" in error_lower:
            return "not_found"
        if "permission" in error_lower or "access denied" in error_lower:
            return "permission"
        if "timeout" in error_lower:
            return "timeout"
        if "connection" in error_lower or "network" in error_lower:
            return "network"
        if "syntax" in error_lower or "parse" in error_lower:
            return "syntax"
        return "unknown"


critic = Critic()
