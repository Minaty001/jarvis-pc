# task_engine/approval.py
"""Approval Engine — Risk-gated human-in-the-loop confirmations."""
from __future__ import annotations
import asyncio, uuid
from enum import Enum
from typing import Any, Callable, Optional
from config.logger import get_logger
from task_engine.models import TaskStep

logger = get_logger("task_engine.approval")

# Tools that always need approval (high/critical risk)
_HIGH_RISK_TOOLS = {
    "run_command", "shell_exec", "delete_file", "send_email",
    "send_message", "transfer_file", "format_disk",
}
_CRITICAL_TOOLS: set[str] = set()  # always-confirm, no auto-grant ever

_DANGEROUS_PATTERNS = [
    "rm ", "rm-rf", "del ", "format ", "mkfs", "sudo", "chmod 777",
    "wget", "curl -o", "> /dev/", "dd if=",
]


class ApprovalState(str, Enum):
    PENDING = "PENDING"
    GRANTED = "GRANTED"
    DENIED = "DENIED"
    TIMEOUT = "TIMEOUT"


class PendingApproval:
    def __init__(self, task_id: str, step: TaskStep):
        self.id = f"appr-{uuid.uuid4().hex[:8]}"
        self.task_id = task_id
        self.step = step
        self.state = ApprovalState.PENDING
        self._event = asyncio.Event()

    def decide(self, granted: bool) -> None:
        self.state = ApprovalState.GRANTED if granted else ApprovalState.DENIED
        self._event.set()


class ApprovalEngine:
    """Manages risk-based approval gates for task steps."""

    def __init__(self):
        self._pending: dict[str, PendingApproval] = {}

    def needs_approval(self, tool_name: str, params: dict) -> bool:
        """Returns True if this tool+params combo requires human approval."""
        if tool_name in _CRITICAL_TOOLS or tool_name in _HIGH_RISK_TOOLS:
            return True
        # Check dangerous command patterns
        cmd = params.get("command", "") or params.get("cmd", "")
        if cmd:
            cmd_lower = cmd.lower()
            if any(p in cmd_lower for p in _DANGEROUS_PATTERNS):
                return True
        return False

    def filter_risky(self, steps: list[TaskStep]) -> list[TaskStep]:
        """Return the subset of steps that require approval."""
        return [s for s in steps if self.needs_approval(s.action, s.parameters)]

    async def request_approval(
        self,
        task_id: str,
        step: TaskStep,
        notify_cb: Callable,
    ) -> str:
        """Create a pending approval and notify user. Returns approval_id."""
        appr = PendingApproval(task_id=task_id, step=step)
        self._pending[appr.id] = appr
        logger.info("Approval requested: %s for step %s (%s)", appr.id, step.id, step.action)
        await notify_cb({
            "approval_id": appr.id,
            "task_id": task_id,
            "step": step.name,
            "action": step.action,
            "parameters": step.parameters,
        })
        return appr.id

    async def wait_for_decision(self, approval_id: str, timeout: float = 300.0) -> bool:
        """Block until user grants/denies or timeout. Returns True if granted."""
        appr = self._pending.get(approval_id)
        if not appr:
            return False
        try:
            await asyncio.wait_for(appr._event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            appr.state = ApprovalState.TIMEOUT
            logger.warning("Approval %s timed out", approval_id)
            return False
        return appr.state == ApprovalState.GRANTED

    def grant(self, approval_id: str) -> None:
        appr = self._pending.get(approval_id)
        if appr:
            appr.decide(True)
            logger.info("Approval %s granted", approval_id)

    def deny(self, approval_id: str) -> None:
        appr = self._pending.get(approval_id)
        if appr:
            appr.decide(False)
            logger.info("Approval %s denied", approval_id)

    def pending_approvals(self) -> list[dict]:
        return [
            {"id": a.id, "task_id": a.task_id, "step": a.step.name, "action": a.step.action}
            for a in self._pending.values()
            if a.state == ApprovalState.PENDING
        ]


approval_engine = ApprovalEngine()
