import pytest
from jarvis.tools.executor import (
    ToolExecutor,
    ToolDefinition,
    RiskLevel,
    ToolDenied,
    ConfirmationRequired,
)

@pytest.mark.asyncio
async def test_tool_executor_safe():
    executor = ToolExecutor()
    async def sample_handler(val: str):
        return f"result-{val}"

    executor.register(ToolDefinition("safe_tool", RiskLevel.SAFE, sample_handler))
    res = await executor.execute("safe_tool", val="123")
    assert res == "result-123"

from jarvis.tools.confirmation import create_confirmation_token

@pytest.mark.asyncio
async def test_tool_executor_confirm_requires_flag():
    executor = ToolExecutor()
    async def confirm_handler():
        return "done"

    executor.register(ToolDefinition("confirm_tool", RiskLevel.CONFIRM, confirm_handler))
    with pytest.raises(ConfirmationRequired):
        await executor.execute("confirm_tool")

    token = create_confirmation_token("confirm_tool", None, "", "jarvis-default-secret")
    res = await executor.execute("confirm_tool", confirmation_token=token)
    assert res == "done"

@pytest.mark.asyncio
async def test_tool_executor_forbidden_denied():
    executor = ToolExecutor()
    async def forbidden_handler():
        return "bad"

    executor.register(ToolDefinition("forbidden_tool", RiskLevel.FORBIDDEN, forbidden_handler))
    with pytest.raises(ToolDenied):
        await executor.execute("forbidden_tool")

@pytest.mark.asyncio
async def test_tool_executor_privileged_denied():
    executor = ToolExecutor()
    async def privileged_handler():
        return "admin"

    executor.register(ToolDefinition("privileged_tool", RiskLevel.PRIVILEGED, privileged_handler))
    with pytest.raises(ToolDenied):
        await executor.execute("privileged_tool")

@pytest.mark.asyncio
async def test_tool_executor_unknown_tool():
    executor = ToolExecutor()
    with pytest.raises(KeyError):
        await executor.execute("non_existent_tool")
