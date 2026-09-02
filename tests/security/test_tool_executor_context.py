import pytest
from jarvis.cognitive.context import ExecutionContext
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.executor import ToolExecutor
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel

@pytest.mark.asyncio
async def test_tool_executor_with_context():
    registry = ToolRegistry()
    executed = []
    async def dummy(arg: str):
        executed.append(arg)
        return "ok"

    registry.register(ToolDefinition("test_tool", RiskLevel.SAFE, frozenset(), dummy))
    executor = ToolExecutor(registry)
    ctx = ExecutionContext(session_id="s1", task_id="t1", user_id="u1", request_id="r1")

    res = await executor.execute("test_tool", context=ctx, arg="val")
    assert res == "ok"
    assert executed == ["val"]

@pytest.mark.asyncio
async def test_tool_executor_with_context_and_arguments_dict():
    registry = ToolRegistry()
    executed = []
    async def dummy(arg: str):
        executed.append(arg)
        return "ok"

    registry.register(ToolDefinition("test_tool_dict", RiskLevel.SAFE, frozenset(), dummy))
    executor = ToolExecutor(registry)
    ctx = ExecutionContext(session_id="s1", task_id="t1", user_id="u1", request_id="r1")

    res = await executor.execute(tool_name="test_tool_dict", context=ctx, arguments={"arg": "val"})
    assert res == "ok"
    assert executed == ["val"]
