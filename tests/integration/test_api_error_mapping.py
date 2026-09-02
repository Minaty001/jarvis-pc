import pytest
from fastapi.testclient import TestClient

from jarvis.api.app import app, get_tool_executor
from jarvis.config.settings import get_settings
from jarvis.tools.base import ToolDefinition
from jarvis.tools.executor import ConfirmationRequired, RiskLevel, ToolDenied
from jarvis.tools.rate_limit import RateLimitExceeded

client = TestClient(app)


@pytest.fixture(autouse=True)
def set_dev_env(monkeypatch):
    monkeypatch.setenv("JARVIS_ENVIRONMENT", "development")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_api_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_tool_denied_returns_403():
    executor = get_tool_executor()

    async def forbidden_handler():
        return "ok"

    executor.register(
        ToolDefinition(
            name="forbidden_tool",
            risk_level=RiskLevel.FORBIDDEN,
            handler=forbidden_handler,
        )
    )

    res = client.post("/execute", json={"tool": "forbidden_tool"})
    assert res.status_code == 403
    assert "denied" in res.json()["detail"].lower()


def test_confirmation_required_returns_409():
    executor = get_tool_executor()

    async def sensitive_handler():
        return "confirmed_ok"

    executor.register(
        ToolDefinition(
            name="sensitive_tool",
            risk_level=RiskLevel.CONFIRM,
            handler=sensitive_handler,
        )
    )

    res = client.post("/execute", json={"tool": "sensitive_tool", "confirmed": False})
    assert res.status_code == 409
    assert "confirmation" in res.json()["detail"].lower()


def test_rate_limit_exceeded_returns_429(monkeypatch):
    executor = get_tool_executor()

    async def limited_handler():
        return "rate_ok"

    executor.register(
        ToolDefinition(
            name="limited_tool",
            risk_level=RiskLevel.SAFE,
            handler=limited_handler,
        )
    )

    def mock_check(key: str):
        raise RateLimitExceeded("Rate limit exceeded for limited_tool")

    monkeypatch.setattr(executor.rate_limiter, "check", mock_check)

    res = client.post("/execute", json={"tool": "limited_tool"})
    assert res.status_code == 429
    assert "rate limit exceeded" in res.json()["detail"].lower()


def test_value_error_returns_400():
    executor = get_tool_executor()

    async def invalid_args_handler():
        raise ValueError("Invalid argument value")

    executor.register(
        ToolDefinition(
            name="value_error_tool",
            risk_level=RiskLevel.SAFE,
            handler=invalid_args_handler,
        )
    )

    res = client.post("/execute", json={"tool": "value_error_tool"})
    assert res.status_code == 400
    assert "invalid argument value" in res.json()["detail"].lower()


def test_production_auth_mandatory_without_token(monkeypatch):
    monkeypatch.setenv("JARVIS_ENVIRONMENT", "production")
    monkeypatch.delenv("JARVIS_API_TOKEN", raising=False)
    get_settings.cache_clear()

    res = client.get("/health")
    # Health endpoint should work without auth
    assert res.status_code == 200

    # Execute endpoint without token in production must be 401
    res = client.post("/execute", json={"tool": "any_tool"})
    assert res.status_code == 401
    assert "production" in res.json()["detail"].lower() or "token" in res.json()["detail"].lower()
