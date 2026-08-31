# tests/task_engine/test_approval.py
import asyncio, pytest
from unittest.mock import AsyncMock, MagicMock
from task_engine.models import TaskStep
from task_engine.approval import ApprovalEngine

def test_safe_tool_no_approval_needed():
    engine = ApprovalEngine()
    # web_search is LOW risk — no approval
    assert engine.needs_approval("web_search", {"query": "weather"}) is False

def test_high_risk_tool_needs_approval():
    engine = ApprovalEngine()
    assert engine.needs_approval("run_command", {"command": "rm -rf /tmp/test"}) is True

def test_grant_unblocks_waiting():
    engine = ApprovalEngine()
    step = TaskStep(task_id="t-1", name="delete", action="run_command",
                    parameters={"command": "rm file.txt"})
    notify = AsyncMock()

    async def run():
        pending_id = await engine.request_approval("t-1", step, notify)
        # grant immediately
        engine.grant(pending_id)
        result = await engine.wait_for_decision(pending_id, timeout=2.0)
        return result

    result = asyncio.get_event_loop().run_until_complete(run())
    assert result is True

def test_deny_blocks_execution():
    engine = ApprovalEngine()
    step = TaskStep(task_id="t-1", name="delete", action="run_command",
                    parameters={"command": "rm file.txt"})

    async def run():
        pending_id = await engine.request_approval("t-1", step, AsyncMock())
        engine.deny(pending_id)
        result = await engine.wait_for_decision(pending_id, timeout=2.0)
        return result

    result = asyncio.get_event_loop().run_until_complete(run())
    assert result is False

def test_approval_timeout_denies():
    engine = ApprovalEngine()
    step = TaskStep(task_id="t-1", name="delete", action="run_command",
                    parameters={"command": "rm file.txt"})

    async def run():
        pending_id = await engine.request_approval("t-1", step, AsyncMock())
        result = await engine.wait_for_decision(pending_id, timeout=0.1)
        return result

    result = asyncio.get_event_loop().run_until_complete(run())
    assert result is False  # timeout = deny

def test_batch_approval_groups_risky_steps():
    engine = ApprovalEngine()
    steps = [
        TaskStep(task_id="t-1", name="search", action="web_search", parameters={"query": "test"}),
        TaskStep(task_id="t-1", name="delete", action="run_command", parameters={"command": "rm x"}),
        TaskStep(task_id="t-1", name="send", action="run_command", parameters={"command": "mail y"}),
    ]
    risky = engine.filter_risky(steps)
    assert len(risky) == 2
