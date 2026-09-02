import pytest
from jarvis.tools.executor import ToolExecutor
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel
from jarvis.cognitive.context import ExecutionContext


@pytest.mark.asyncio
async def test_executor_rejects_missing_context():
    """execute() must raise TypeError when context is not provided."""
    registry = ToolRegistry()
    async def dummy(): return "ok"
    registry.register(ToolDefinition("test_tool", RiskLevel.SAFE, frozenset(), dummy))
    executor = ToolExecutor(registry)
    with pytest.raises(TypeError):
        await executor.execute("test_tool", arguments={})


@pytest.mark.asyncio
async def test_capabilities_always_enforced():
    """Capabilities must be checked even for seemingly simple calls."""
    registry = ToolRegistry()
    async def dummy(): return "ok"
    registry.register(ToolDefinition("write_file", RiskLevel.SAFE, frozenset({"filesystem.write"}), dummy))
    executor = ToolExecutor(registry)
    ctx = ExecutionContext("s1", "t1", "u1", "r1", permissions=frozenset())
    from jarvis.tools.executor import ToolDenied
    with pytest.raises(ToolDenied):
        await executor.execute("write_file", context=ctx)
