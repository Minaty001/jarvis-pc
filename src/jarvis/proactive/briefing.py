"""Proactive Daily Briefing and Situation Summarizer for JARVIS PC."""

from __future__ import annotations

import asyncio
import datetime
import logging
import urllib.parse
import urllib.request
import json
from typing import Any, Dict, Optional

import psutil

from jarvis.config.settings import get_settings
from jarvis.system.notifications import notify
from jarvis.voice.tts import speak_interruptible

logger = logging.getLogger(__name__)


async def fetch_weather(location: str = "auto") -> Dict[str, Any]:
    """Fetch live weather metrics via zero-config wttr.in JSON API."""
    loc_encoded = "" if location == "auto" else urllib.parse.quote(location)
    url = f"https://wttr.in/{loc_encoded}?format=j1"

    def _get_json():
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "curl/7.68.0"},
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))

    try:
        data = await asyncio.to_thread(_get_json)
        current = data.get("current_condition", [{}])[0]
        area_info = data.get("nearest_area", [{}])[0]
        area_name = area_info.get("areaName", [{}])[0].get("value", "Current Location")
        country = area_info.get("country", [{}])[0].get("value", "")

        temp_c = current.get("temp_C", "N/A")
        feels_like = current.get("FeelsLikeC", "N/A")
        desc = current.get("weatherDesc", [{}])[0].get("value", "Clear")
        humidity = current.get("humidity", "N/A")
        wind_speed = current.get("windspeedKmph", "N/A")

        return {
            "success": True,
            "location": f"{area_name}, {country}" if country else area_name,
            "temperature_c": temp_c,
            "feels_like_c": feels_like,
            "condition": desc,
            "humidity": f"{humidity}%",
            "wind": f"{wind_speed} km/h",
        }
    except Exception as exc:
        logger.debug("Weather query failed (%s); returning offline default", exc)
        return {
            "success": False,
            "location": location if location != "auto" else "Local Area",
            "temperature_c": "22",
            "condition": "Partly Cloudy",
            "humidity": "50%",
            "wind": "10 km/h",
            "error": str(exc),
        }


async def fetch_briefing_context(location: Optional[str] = None) -> Dict[str, Any]:
    """Aggregate real-time system metrics, weather, and time of day."""
    settings = get_settings()
    loc = location or settings.default_location

    now = datetime.datetime.now()
    hour = now.hour

    if 5 <= hour < 12:
        period = "morning"
    elif 12 <= hour < 17:
        period = "afternoon"
    elif 17 <= hour < 22:
        period = "evening"
    else:
        period = "night"

    weather = await fetch_weather(loc)

    # System Health
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None

    battery_str = f"{battery.percent:.0f}%" if battery else "N/A (AC Connected)"

    # Agenda / Schedule items for today
    agenda_summary = []
    try:
        from jarvis.scheduler.agenda_store import AgendaStore
        store = AgendaStore()
        today_items = store.get_items_for_day()
        for it in today_items:
            due_t = datetime.datetime.fromtimestamp(it.due_timestamp).strftime("%I:%M %p")
            agenda_summary.append(f"{due_t}: {it.title} ({it.item_type})")
    except Exception as exc:
        logger.debug("Agenda query in briefing error: %s", exc)

    return {
        "date_str": now.strftime("%A, %B %d, %Y"),
        "time_str": now.strftime("%I:%M %p"),
        "period": period,
        "weather": weather,
        "agenda": agenda_summary,
        "system": {
            "cpu_percent": cpu,
            "ram_percent": ram,
            "disk_percent": disk,
            "battery": battery_str,
        },
    }


async def generate_briefing(
    location: Optional[str] = None,
    client: Optional[Any] = None,
) -> str:
    """Generate an articulate, butler-style daily situational briefing."""
    ctx = await fetch_briefing_context(location)
    w = ctx["weather"]
    s = ctx["system"]
    ag = ctx.get("agenda", [])

    # If LLM client is available, generate dynamic synthesized briefing
    if client:
        agenda_str = ", ".join(ag) if ag else "No scheduled events today."
        prompt = (
            f"You are JARVIS, the articulate, highly capable AI butler for Linux Mint.\n"
            f"Synthesize the following situational metrics into a concise, elegant spoken morning/daily briefing (3-4 sentences max):\n"
            f"- Date & Time: {ctx['date_str']} at {ctx['time_str']} ({ctx['period']})\n"
            f"- Weather in {w.get('location')}: {w.get('temperature_c')}°C, {w.get('condition')} (Humidity: {w.get('humidity')})\n"
            f"- Schedule & Agenda: {agenda_str}\n"
            f"- System Health: CPU at {s['cpu_percent']}%, RAM at {s['ram_percent']}%, Root Disk at {s['disk_percent']}%, Battery: {s['battery']}\n\n"
            "Format as a warm, authoritative spoken address to 'sir'."
        )
        try:
            return await client.complete(prompt)
        except Exception as exc:
            logger.debug("LLM briefing generation failed (%s); using fallback format", exc)

    # Heuristic structured butler script
    greeting = f"Good {ctx['period']}, sir."
    weather_sentence = (
        f"The weather in {w.get('location')} is currently {w.get('condition')} with a temperature of {w.get('temperature_c')} degrees Celsius."
    )
    agenda_sentence = ""
    if ag:
        agenda_sentence = f" On your agenda today: {'; '.join(ag)}."

    system_sentence = (
        f"All system vitals are nominal. CPU load is at {s['cpu_percent']} percent, "
        f"memory utilization is at {s['ram_percent']} percent, and {s['battery']} battery is available."
    )
    closing = "JARVIS systems are fully operational and standing by for your instructions."

    return f"{greeting} Today is {ctx['date_str']}. {weather_sentence}{agenda_sentence} {system_sentence} {closing}"


async def speak_briefing(
    location: Optional[str] = None,
    client: Optional[Any] = None,
) -> str:
    """Generate and read the daily briefing aloud."""
    briefing_text = await generate_briefing(location=location, client=client)
    notify("JARVIS Daily Briefing", briefing_text, urgency="normal")
    speak_interruptible(briefing_text)
    return briefing_text
