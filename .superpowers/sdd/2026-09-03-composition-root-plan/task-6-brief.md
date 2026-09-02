# Task 6 Brief: Use async rate limiter & enforce request body size

**Fixes issues:** #16 (sync check instead of async), #17 (no request size enforcement)

## Problem

1. `ToolExecutor.execute()` calls `self.rate_limiter.check(target_name)` (synchronous). The async version `check_async()` with `asyncio.Lock()` is never used.
2. Settings has `max_request_bytes` but `/execute` endpoint doesn't enforce HTTP body size.

## Files to modify

### 1. MODIFY `src/jarvis/tools/executor.py`

Change:
```python
self.rate_limiter.check(target_name)
```
to:
```python
await self.rate_limiter.check_async(target_name)
```

### 2. MODIFY `src/jarvis/api/app.py`

Add request body size middleware to the `create_api_app` factory:
```python
from jarvis.config.settings import get_settings

@api.middleware("http")
async def limit_request_body(request: Request, call_next):
    settings = get_settings()
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_request_bytes:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"detail": f"Request body exceeds {settings.max_request_bytes} bytes"}
        )
    return await call_next(request)
```

### 3. WRITE TEST `tests/security/test_rate_limit_and_body_size.py`

```python
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
```

## Execution steps

1. Write test `tests/security/test_rate_limit_and_body_size.py`
2. Run: `PYTHONPATH=src pytest tests/security/test_rate_limit_and_body_size.py`
3. Modify `src/jarvis/tools/executor.py` and `src/jarvis/api/app.py`
4. Run test again
5. Run: `PYTHONPATH=src pytest tests/security/`
6. Commit: `git add -A && git commit -m "security(api): use async rate limiter and enforce HTTP request body size limits"`
7. Write report to `/home/shanu/Desktop/jarvis-pc/.superpowers/sdd/2026-09-03-composition-root-plan/task-6-report.md`
