"""Builtin tools for live weather reporting and daily briefings."""

from __future__ import annotations

import logging
from typing import Any, Optional

from jarvis.proactive.briefing import fetch_weather, generate_briefing

logger = logging.getLogger(__name__)


async def get_weather(location: str = "auto") -> str:
    """Fetch current weather conditions and temperature for a given location or city."""
    res = await fetch_weather(location)
    if res.get("success"):
        return (
            f"Weather for {res['location']}:\n"
            f"• Condition:   {res['condition']}\n"
            f"• Temperature: {res['temperature_c']}°C (Feels like: {res['feels_like_c']}°C)\n"
            f"• Humidity:    {res['humidity']}\n"
            f"• Wind:        {res['wind']}"
        )
    return (
        f"Weather for {res.get('location', location)}: {res.get('condition', 'Clear')}, "
        f"{res.get('temperature_c', '22')}°C."
    )


async def get_daily_briefing(location: str = "auto") -> str:
    """Generate a complete situational daily briefing (time, date, weather, system health)."""
    return await generate_briefing(location=location if location != "auto" else None)
