import pytest
from httpx import AsyncClient, ASGITransport
from jarvis.api.app import create_api_app
from jarvis.tools.executor import ToolExecutor
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel


@pytest.mark.asyncio
async def test_request_body_too_large():
    executor = ToolExecutor(ToolRegistry())
    api = create_api_app(executor)
    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        big_body = "x" * 2_000_000
        response = await client.post(
            "/execute",
            json={"tool": "test", "arguments": {"data": big_body}},
            headers={"content-length": str(len(big_body))},
        )
        assert response.status_code == 413


@pytest.mark.asyncio
async def test_rate_limiter_uses_async_check():
    """Verify executor calls check_async, not check."""
    from jarvis.tools.rate_limit import RateLimiter
    from jarvis.cognitive.context import ExecutionContext

    calls = []
    class TrackingLimiter(RateLimiter):
        async def check_async(self, key):
            calls.append(("async", key))
            return True
        def check(self, key):
            calls.append(("sync", key))
            return True

    registry = ToolRegistry()
    async def dummy(): return "ok"
    registry.register(ToolDefinition("t", RiskLevel.SAFE, frozenset(), dummy))
    executor = ToolExecutor(registry, rate_limiter=TrackingLimiter())
    ctx = ExecutionContext("s", "t", "u", "r")
    await executor.execute("t", context=ctx)
    assert ("async", "t") in calls
    assert ("sync", "t") not in calls
