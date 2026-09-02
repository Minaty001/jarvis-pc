import logging
import pytest
from jarvis.tools.rate_limit import RateLimiter, RateLimitExceeded
from jarvis.tools.audit import AuditLogger, redact_secrets
from jarvis.tools.executor import ToolExecutor
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel
from jarvis.cognitive.context import ExecutionContext


def test_rate_limiter_blocks_excessive_calls():
    limiter = RateLimiter(max_calls=2, period_seconds=60)
    assert limiter.check("open_app") is True
    assert limiter.check("open_app") is True
    with pytest.raises(RateLimitExceeded):
        limiter.check("open_app")


def test_secret_redaction():
    log_data = {"key": "secret-api-token-12345", "tool": "test"}
    redacted = redact_secrets(log_data)
    assert redacted["key"] == "[REDACTED]"


def test_secret_redaction_nested_and_keys():
    log_data = {
        "api_key": "12345",
        "authorization": "Bearer token",
        "nested": {"password": "p1", "safe": "hello"},
        "user_secret_data": "shh",
    }
    redacted = redact_secrets(log_data)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "hello"
    assert redacted["user_secret_data"] == "[REDACTED]"


def test_audit_logger_output(caplog):
    caplog.set_level(logging.INFO)
    logger = AuditLogger()
    logger.log_execution(
        request_id="req-123",
        tool_name="test_tool",
        risk="safe",
        status="success",
        arguments={"api_key": "my-secret-key", "param": "value"},
    )
    assert "AUDIT" in caplog.text
    assert "req-123" in caplog.text
    assert "test_tool" in caplog.text
    assert "[REDACTED]" in caplog.text
    assert "my-secret-key" not in caplog.text


@pytest.mark.asyncio
async def test_tool_executor_enforces_rate_limit():
    limiter = RateLimiter(max_calls=1, period_seconds=60)
    executor = ToolExecutor(rate_limiter=limiter)

    async def dummy_handler():
        return "ok"

    executor.register(ToolDefinition("test_tool", RiskLevel.SAFE, dummy_handler))

    ctx = ExecutionContext(session_id="s1", task_id="t1", user_id="u1", request_id="r1")
    res = await executor.execute("test_tool", context=ctx)
    assert res == "ok"

    with pytest.raises(RateLimitExceeded):
        await executor.execute("test_tool", context=ctx)


@pytest.mark.asyncio
async def test_tool_executor_logs_audit(caplog):
    caplog.set_level(logging.INFO)
    audit = AuditLogger()
    executor = ToolExecutor(audit_logger=audit)

    async def dummy_handler(password: str):
        return "ok"

    executor.register(ToolDefinition("auth_tool", RiskLevel.SAFE, dummy_handler))
    ctx = ExecutionContext(session_id="s1", task_id="t1", user_id="u1", request_id="req-999")

    res = await executor.execute("auth_tool", password="my_password", context=ctx)
    assert res == "ok"
    assert "AUDIT" in caplog.text
    assert "req-999" in caplog.text
    assert "auth_tool" in caplog.text
    assert "[REDACTED]" in caplog.text
    assert "my_password" not in caplog.text
