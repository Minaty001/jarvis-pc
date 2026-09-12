import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from jarvis.api.app import create_api_app
from jarvis.tools.executor import ToolExecutor
from jarvis.config.settings import get_settings


@pytest.fixture(autouse=True)
def set_dev_env(monkeypatch):
    monkeypatch.setenv("JARVIS_ENVIRONMENT", "development")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_chat_endpoint_sanitizes_internal_error():
    """Ensure internal errors do not leak system exception details to API clients."""
    executor = ToolExecutor()
    fake_agent = AsyncMock()
    fake_agent.respond.side_effect = RuntimeError("Sensitive internal database connection leak")

    app = create_api_app(executor, agent=fake_agent)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 500
    detail = response.json().get("detail", "")
    assert "internal error" in detail.lower()
    assert "database connection leak" not in detail
    assert "Sensitive" not in detail
