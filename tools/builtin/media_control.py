"""Media Control — Play, pause, volume."""

import subprocess
from typing import Any

from config.logger import get_logger

logger = get_logger("tools.media_control")


def media_play(query: str = "") -> dict[str, Any]:
    """Play media using mpv or default player."""
    try:
        if query:
            subprocess.Popen(
                ["mpv", f"https://www.youtube.com/results?search_query={query}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.run(["playerctl", "play"], capture_output=True)
        return {"success": True, "result": f"Playing {query}" if query else "Playing"}
    except Exception as e:
        return {"success": False, "result": f"Play failed: {e}"}


def media_pause() -> dict[str, Any]:
    try:
        subprocess.run(["playerctl", "pause"], capture_output=True)
        return {"success": True, "result": "Paused"}
    except Exception as e:
        return {"success": False, "result": f"Pause failed: {e}"}


def set_volume(level: str) -> dict[str, Any]:
    try:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"], capture_output=True)
        return {"success": True, "result": f"Volume set to {level}%"}
    except Exception as e:
        return {"success": False, "result": f"Volume failed: {e}"}
