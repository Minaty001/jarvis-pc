from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock

from jarvis.tools.audit import redact_secrets
from jarvis.tools.rate_limit import RateLimiter
from jarvis.system.process import run_process, MAX_OUTPUT_BYTES
from jarvis.app.application import Application


def test_regex_secret_pattern_redaction():
    data = {
        "args": ["token", "sk-1234567890abcdefghijkl"],
        "jwt": ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",),
        "nested": {"set_data": {"sk-999999999999999"}},
    }
    cleaned = redact_secrets(data)
    assert "sk-1234567890" not in str(cleaned)
    assert "eyJhbGciOiJI" not in str(cleaned)
    assert "sk-999999999" not in str(cleaned)
    assert cleaned["args"][0] == "[REDACTED]"


@pytest.mark.asyncio
async def test_rate_limiter_async_lock():
    limiter = RateLimiter(max_calls=5, period_seconds=60)
    tasks = [asyncio.create_task(limiter.check_async("test_key")) for _ in range(5)]
    results = await asyncio.gather(*tasks)
    assert all(results)


@pytest.mark.asyncio
async def test_bounded_process_output():
    assert MAX_OUTPUT_BYTES == 10 * 1024 * 1024
    res = await run_process(["echo", "hello"])
    assert res.returncode == 0
    assert res.stdout.strip() == "hello"


@pytest.mark.asyncio
async def test_application_startup_rollback():
    comp1 = AsyncMock()
    comp1.start = AsyncMock()
    comp1.stop = AsyncMock()

    comp2 = AsyncMock()
    comp2.start = AsyncMock(side_effect=RuntimeError("Startup error in comp2"))
    comp2.stop = AsyncMock()

    app = Application(scheduler=comp1, voice=comp2)
    with pytest.raises(RuntimeError, match="Startup error in comp2"):
        await app.start()

    comp1.start.assert_called_once()
    comp1.stop.assert_called_once()
    comp2.start.assert_called_once()
    comp2.stop.assert_not_called()
    assert not app.is_started
