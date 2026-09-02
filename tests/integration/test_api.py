import pytest
from fastapi.testclient import TestClient

from jarvis.api.app import app, get_tool_executor
from jarvis.config.settings import get_settings
from jarvis.tools.executor import RiskLevel, ToolDefinition

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_execute_endpoint_unknown_tool():
    response = client.post("/execute", json={"tool": "nonexistent_tool"})
    assert response.status_code == 400
    assert "unknown tool" in response.json()["detail"].lower()


def test_execute_endpoint_success():
    executor = get_tool_executor()

    async def sample_tool(param1: str):
        return f"processed: {param1}"

    executor.register(
        ToolDefinition(
            name="sample_tool",
            risk_level=RiskLevel.SAFE,
            handler=sample_tool,
        )
    )

    response = client.post(
        "/execute",
        json={"tool": "sample_tool", "arguments": {"param1": "hello"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["result"] == "processed: hello"


def test_execute_endpoint_auth_required(monkeypatch):
    executor = get_tool_executor()

    async def dummy_tool():
        return "auth_ok"

    executor.register(
        ToolDefinition(
            name="dummy_tool",
            risk_level=RiskLevel.SAFE,
            handler=dummy_tool,
        )
    )

    monkeypatch.setenv("JARVIS_API_TOKEN", "secret123")
    get_settings.cache_clear()

    try:
        # Request without header should fail with 401
        response = client.post("/execute", json={"tool": "dummy_tool"})
        assert response.status_code == 401

        # Request with wrong token should fail with 401
        response = client.post(
            "/execute",
            json={"tool": "dummy_tool"},
            headers={"Authorization": "Bearer wrongtoken"},
        )
        assert response.status_code == 401

        # Request with correct token should succeed
        response = client.post(
            "/execute",
            json={"tool": "dummy_tool"},
            headers={"Authorization": "Bearer secret123"},
        )
        assert response.status_code == 200
        assert response.json()["result"] == "auth_ok"
    finally:
        get_settings.cache_clear()
