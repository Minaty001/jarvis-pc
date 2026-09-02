import time
import pytest
from jarvis.tools.confirmation import create_confirmation_token, verify_confirmation_token


def test_valid_token_accepted():
    token = create_confirmation_token("tool", {"a": 1}, "s1", "secret")
    assert verify_confirmation_token("tool", {"a": 1}, "s1", "secret", token)


def test_expired_token_rejected(monkeypatch):
    token = create_confirmation_token("tool", {"a": 1}, "s1", "secret", ttl=1)
    import jarvis.tools.confirmation as conf
    monkeypatch.setattr(conf.time, "time", lambda: time.time() + 10)
    assert not verify_confirmation_token("tool", {"a": 1}, "s1", "secret", token)


def test_wrong_tool_rejected():
    token = create_confirmation_token("tool_a", {"a": 1}, "s1", "secret")
    assert not verify_confirmation_token("tool_b", {"a": 1}, "s1", "secret", token)


def test_tampered_token_rejected():
    token = create_confirmation_token("tool", {"a": 1}, "s1", "secret")
    assert not verify_confirmation_token("tool", {"a": 1}, "s1", "secret", token + "x")


@pytest.mark.asyncio
async def test_missing_secret_fails_closed():
    from jarvis.tools.executor import ToolExecutor, ToolDenied
    from jarvis.tools.registry import ToolRegistry
    from jarvis.tools.base import ToolDefinition
    from jarvis.tools.policy import RiskLevel
    from jarvis.cognitive.context import ExecutionContext

    registry = ToolRegistry()
    async def dummy(): return "ok"
    registry.register(ToolDefinition("risky", RiskLevel.CONFIRM, frozenset(), dummy))
    executor = ToolExecutor(registry)  # No confirmation_secret
    ctx = ExecutionContext("s1", "t1", "u1", "r1")

    with pytest.raises(ToolDenied):
        await executor.execute("risky", context=ctx, confirmation_token="fake", arguments={})
