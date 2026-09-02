import pytest
from jarvis.tools.executor import ToolExecutor, ToolDenied, ConfirmationRequired
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel
from jarvis.cognitive.context import ExecutionContext
from jarvis.tools.confirmation import create_confirmation_token


@pytest.mark.asyncio
async def test_capability_authorization_enforced():
    registry = ToolRegistry()
    async def dummy(): return "ok"
    registry.register(ToolDefinition("write_file", RiskLevel.SAFE, frozenset(["filesystem.write"]), dummy))
    executor = ToolExecutor(registry)

    ctx = ExecutionContext("s1", "t1", "u1", "r1", permissions=frozenset(["filesystem.read"]))
    with pytest.raises(ToolDenied, match="Insufficient capabilities"):
        await executor.execute("write_file", context=ctx)


@pytest.mark.asyncio
async def test_capability_authorization_succeeds():
    registry = ToolRegistry()
    async def dummy(): return "ok"
    registry.register(ToolDefinition("write_file", RiskLevel.SAFE, frozenset(["filesystem.write"]), dummy))
    executor = ToolExecutor(registry)

    ctx = ExecutionContext("s1", "t1", "u1", "r1", permissions=frozenset(["filesystem.write", "filesystem.read"]))
    res = await executor.execute("write_file", context=ctx)
    assert res == "ok"


@pytest.mark.asyncio
async def test_confirmation_token_required_for_confirm_risk():
    registry = ToolRegistry()
    async def dummy(**kwargs): return "ok"
    registry.register(ToolDefinition("send_msg", RiskLevel.CONFIRM, frozenset(), dummy))
    executor = ToolExecutor(registry)
    ctx = ExecutionContext("s1", "t1", "u1", "r1")

    with pytest.raises(ConfirmationRequired):
        await executor.execute("send_msg", context=ctx, arguments={"to": "alice"})

    secret = "secret-key"
    token = create_confirmation_token("send_msg", {"to": "alice"}, "s1", secret)
    res = await executor.execute("send_msg", context=ctx, confirmation_token=token, secret=secret, arguments={"to": "alice"})
    assert res == "ok"


@pytest.mark.asyncio
async def test_confirmation_token_invalid_or_tampered():
    registry = ToolRegistry()
    async def dummy(**kwargs): return "ok"
    registry.register(ToolDefinition("send_msg", RiskLevel.CONFIRM, frozenset(), dummy))
    executor = ToolExecutor(registry)
    ctx = ExecutionContext("s1", "t1", "u1", "r1")

    secret = "secret-key"
    invalid_token = "invalid-token-digest"
    with pytest.raises(ToolDenied, match="Invalid or tampered confirmation token"):
        await executor.execute("send_msg", context=ctx, confirmation_token=invalid_token, secret=secret, arguments={"to": "alice"})


@pytest.mark.asyncio
async def test_confirmed_parameter_not_injected_into_handler():
    registry = ToolRegistry()
    received_kwargs = {}
    async def dummy(**kwargs):
        received_kwargs.update(kwargs)
        return "ok"
    registry.register(ToolDefinition("safe_action", RiskLevel.SAFE, frozenset(), dummy))
    executor = ToolExecutor(registry)
    ctx = ExecutionContext("s1", "t1", "u1", "r1")

    await executor.execute("safe_action", context=ctx, arguments={"data": "test"})
    assert "confirmed" not in received_kwargs
