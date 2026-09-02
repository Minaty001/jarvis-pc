import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.executor import ToolExecutor
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel
from jarvis.tasks.models import TaskPlan, TaskStep
from jarvis.tasks.manager import TaskManager
from jarvis.cognitive.context import ExecutionContext



@pytest.mark.asyncio
async def test_task_manager_routes_exclusively_through_executor():
    registry = ToolRegistry()
    executed_args = []

    async def mock_handler(target: str, **kwargs):
        executed_args.append(target)
        return f"done-{target}"

    registry.register(ToolDefinition("test_tool", RiskLevel.SAFE, frozenset(), mock_handler))
    executor = ToolExecutor(registry)
    manager = TaskManager(executor)

    plan = TaskPlan(
        id="plan-1",
        steps=[TaskStep(id="step-1", tool="test_tool", arguments={"target": "abc"})]
    )
    ctx = ExecutionContext(session_id="s1", task_id="t1", user_id="u1", request_id="r1")

    res = await manager.execute_plan(plan, context=ctx)
    assert res["step-1"] == "done-abc"
    assert executed_args == ["abc"]


@pytest.mark.asyncio
async def test_task_engine_default_step_runner_uses_executor(monkeypatch):
    from task_engine.manager import _default_step_runner
    from jarvis.tools.executor import ToolExecutor

    executed = []

    async def mock_execute(self, action, context=None, **kwargs):
        executed.append((action, kwargs))
        return "executor-success"

    monkeypatch.setattr(ToolExecutor, "execute", mock_execute)

    res = await _default_step_runner("test_action", {"foo": "bar"})
    assert res.success is True
    assert res.output == "executor-success"
    assert executed == [("test_action", {"foo": "bar"})]

