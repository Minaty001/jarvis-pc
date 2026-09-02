import asyncio
import threading
import time
import pytest

from jarvis.tools.base import ToolDefinition
from jarvis.tools.executor import ToolExecutor
from jarvis.tools.policy import RiskLevel
from jarvis.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_sync_handler_wrapped_in_thread():
    registry = ToolRegistry()
    main_thread = threading.current_thread()
    executed_thread = None

    def sync_blocking_handler(duration: float):
        nonlocal executed_thread
        executed_thread = threading.current_thread()
        time.sleep(duration)
        return "sync_done"

    registry.register(
        ToolDefinition("sync_tool", RiskLevel.SAFE, frozenset(), sync_blocking_handler)
    )
    executor = ToolExecutor(registry)

    from jarvis.cognitive.context import ExecutionContext
    ctx = ExecutionContext("s1", "t1", "u1", "r1")
    res = await executor.execute("sync_tool", context=ctx, duration=0.01)
    assert res == "sync_done"
    assert executed_thread is not main_thread
