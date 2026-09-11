"""
Unit tests for offline resilience and local LLM fallback (Ollama / Llama-cpp).
"""

from __future__ import annotations

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from jarvis.brain.client import LLMClient, ChatResult, ToolCall


@pytest.mark.asyncio
async def test_cloud_fallback_to_local_on_failure():
    client = LLMClient(
        base_url="https://api.groq.com/openai/v1",
        api_key="real-api-key",
        model="qwen3.8",
        local_base_url="http://localhost:11434/v1",
        local_model="qwen2.5:7b",
        local_enabled=True,
    )

    local_result = ChatResult(
        content="I am replying from local Ollama fallback, sir.",
        tool_calls=[],
        stop_reason="stop",
    )

    # Mock cloud failure and local success
    with patch.object(client, "_call_openai_endpoint") as mock_call:
        # First call (cloud) raises exception, second call (local fallback) returns local_result
        mock_call.side_effect = [
            httpx.ConnectError("Network unreachable"),
            local_result,
        ]

        result = await client.chat(messages=[{"role": "user", "content": "Hello"}])

    assert result.content == "I am replying from local Ollama fallback, sir."
    assert mock_call.call_count == 2


@pytest.mark.asyncio
async def test_no_cloud_key_uses_local_llm():
    client = LLMClient(
        base_url="https://api.groq.com/openai/v1",
        api_key=None,
        local_base_url="http://localhost:11434/v1",
        local_model="qwen2.5:7b",
        local_enabled=True,
    )

    local_result = ChatResult(
        content="Direct local reply.",
        tool_calls=[ToolCall(id="1", name="find_processes", arguments={})],
        stop_reason="tool_calls",
    )

    with patch.object(client, "_call_openai_endpoint", return_value=local_result) as mock_call:
        result = await client.chat(messages=[{"role": "user", "content": "Check processes"}])

    assert result.content == "Direct local reply."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "find_processes"
    mock_call.assert_called_once()


@pytest.mark.asyncio
async def test_both_cloud_and_local_fail_graceful_localbrain():
    client = LLMClient(
        base_url="https://api.groq.com/openai/v1",
        api_key="key",
        local_base_url="http://localhost:11434/v1",
        local_enabled=True,
    )

    with patch.object(client, "_call_openai_endpoint", side_effect=httpx.ConnectError("Down")):
        result = await client.chat(messages=[{"role": "user", "content": "Hello"}])

    assert "higher cognitive functions are not connected" in result.content


@pytest.mark.asyncio
async def test_check_health():
    client = LLMClient(
        base_url="https://api.groq.com/openai/v1",
        api_key="valid-key",
        local_base_url="http://localhost:11434/v1",
        local_enabled=True,
    )

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        health = await client.check_health()

    assert health["cloud"]["available"] is True
    assert health["local"]["enabled"] is True
    assert health["local"]["reachable"] is True
    assert health["active_mode"] == "cloud"
