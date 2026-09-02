import pytest
import asyncio
from jarvis.tasks.cancellation import CancellationToken
from jarvis.tasks.retry import with_retry


def test_cancellation_token():
    token = CancellationToken()
    assert not token.is_cancelled
    token.cancel()
    assert token.is_cancelled


@pytest.mark.asyncio
async def test_with_retry_success_first_attempt():
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        return "success"

    result = await with_retry(operation, max_retries=3, delay_seconds=0.01)
    assert result == "success"
    assert calls == 1


@pytest.mark.asyncio
async def test_with_retry_eventual_success():
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError(f"fail attempt {calls}")
        return "eventual_success"

    result = await with_retry(operation, max_retries=3, delay_seconds=0.01)
    assert result == "eventual_success"
    assert calls == 3


@pytest.mark.asyncio
async def test_with_retry_all_failures_raises_exception():
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        raise RuntimeError("always fail")

    with pytest.raises(RuntimeError, match="always fail"):
        await with_retry(operation, max_retries=3, delay_seconds=0.01)

    assert calls == 3
