"""Unit tests for Proactive Daily Briefing and Weather reporting subsystem."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from jarvis.proactive.briefing import (
    fetch_briefing_context,
    fetch_weather,
    generate_briefing,
    speak_briefing,
)
from jarvis.tools.builtin.weather import get_daily_briefing, get_weather


@pytest.mark.asyncio
async def test_fetch_weather_success():
    fake_wttr = {
        "current_condition": [
            {
                "temp_C": "24",
                "FeelsLikeC": "26",
                "weatherDesc": [{"value": "Sunny"}],
                "humidity": "45",
                "windspeedKmph": "12",
            }
        ],
        "nearest_area": [
            {
                "areaName": [{"value": "London"}],
                "country": [{"value": "United Kingdom"}],
            }
        ],
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = __import__("json").dumps(fake_wttr).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res = await fetch_weather("London")
        assert res["success"] is True
        assert res["temperature_c"] == "24"
        assert res["condition"] == "Sunny"
        assert "London" in res["location"]


@pytest.mark.asyncio
async def test_fetch_weather_fallback_on_error():
    with patch("urllib.request.urlopen", side_effect=Exception("Network down")):
        res = await fetch_weather("Paris")
        assert res["success"] is False
        assert "location" in res
        assert "temperature_c" in res


@pytest.mark.asyncio
async def test_fetch_briefing_context():
    with patch("jarvis.proactive.briefing.fetch_weather") as mock_fw:
        mock_fw.return_value = {
            "success": True,
            "location": "New Delhi, India",
            "temperature_c": "28",
            "condition": "Clear",
            "humidity": "40%",
            "wind": "15 km/h",
        }

        ctx = await fetch_briefing_context("New Delhi")
        assert "date_str" in ctx
        assert "time_str" in ctx
        assert "period" in ctx
        assert "system" in ctx
        assert ctx["system"]["cpu_percent"] >= 0.0
        assert ctx["weather"]["location"] == "New Delhi, India"


@pytest.mark.asyncio
async def test_generate_briefing_heuristic():
    with patch("jarvis.proactive.briefing.fetch_briefing_context") as mock_ctx:
        mock_ctx.return_value = {
            "date_str": "Saturday, September 12, 2026",
            "time_str": "08:00 AM",
            "period": "morning",
            "weather": {
                "location": "Tokyo",
                "temperature_c": "20",
                "condition": "Rainy",
                "humidity": "80%",
            },
            "system": {
                "cpu_percent": 15.0,
                "ram_percent": 42.0,
                "disk_percent": 55.0,
                "battery": "95%",
            },
        }

        briefing = await generate_briefing(location="Tokyo", client=None)
        assert "Good morning, sir." in briefing
        assert "Tokyo" in briefing
        assert "20 degrees Celsius" in briefing
        assert "42.0 percent" in briefing


@pytest.mark.asyncio
async def test_generate_briefing_llm():
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value="Good morning, sir. All systems optimal in London at 22°C.")

    briefing = await generate_briefing(location="London", client=mock_llm)
    assert "Good morning, sir." in briefing
    mock_llm.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_weather_and_briefing_tools():
    with patch("jarvis.tools.builtin.weather.fetch_weather") as mock_fw:
        mock_fw.return_value = {
            "success": True,
            "location": "Sydney",
            "condition": "Sunny",
            "temperature_c": "25",
            "feels_like_c": "26",
            "humidity": "50%",
            "wind": "10 km/h",
        }

        w_out = await get_weather("Sydney")
        assert "Sydney" in w_out
        assert "25°C" in w_out

    with patch("jarvis.tools.builtin.weather.generate_briefing", new_callable=AsyncMock) as mock_gb:
        mock_gb.return_value = "Briefing content here"
        b_out = await get_daily_briefing("auto")
        assert b_out == "Briefing content here"
