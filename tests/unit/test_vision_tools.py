"""
Unit tests for vision analysis tools.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from jarvis.brain.client import ChatResult, LLMClient
from jarvis.tools.builtin.vision import analyze_image


@pytest.mark.asyncio
async def test_analyze_image_outside_home_raises(tmp_path: Path):
    with patch("pathlib.Path.home", return_value=tmp_path):
        with pytest.raises(ValueError, match="must be inside your home directory"):
            await analyze_image("/etc/shadow")


@pytest.mark.asyncio
async def test_analyze_image_nonexistent_raises(tmp_path: Path):
    with patch("pathlib.Path.home", return_value=tmp_path):
        with pytest.raises(FileNotFoundError, match="does not exist"):
            await analyze_image(str(tmp_path / "missing.jpg"))


@pytest.mark.asyncio
async def test_analyze_image_success(tmp_path: Path):
    img = tmp_path / "sample.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0dummy_jpg_content")

    mock_client = AsyncMock()
    mock_client.analyze_image.return_value = "A screenshot displaying a Python terminal with active test results."

    with patch("pathlib.Path.home", return_value=tmp_path):
        res = await analyze_image(str(img), prompt="What is this?", client=mock_client)

    assert "Python terminal" in res
    mock_client.analyze_image.assert_called_once_with(img.resolve(), prompt="What is this?")


@pytest.mark.asyncio
async def test_llm_client_analyze_image_cloud_success(tmp_path: Path):
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\ndummy")

    client = LLMClient(
        base_url="https://api.groq.com/openai/v1",
        api_key="valid-key",
        vision_model="llama-3.2-11b-vision-preview",
    )

    vision_chat_result = ChatResult(
        content="Detected a desktop with Cinnamon panel and open terminal window.",
        tool_calls=[],
        stop_reason="stop",
    )

    with patch.object(client, "_call_openai_endpoint", return_value=vision_chat_result) as mock_call:
        res = await client.analyze_image(img, prompt="Describe")

    assert "Cinnamon panel" in res
    mock_call.assert_called_once()
