"""System-level actions for Linux: Volume, Battery, CPU/RAM, Screenshot, Screen Lock."""

from __future__ import annotations

import datetime
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict

import psutil
from .base import ActionResult, BaseAction


class VolumeAction(BaseAction):
    """Controls system volume via pactl / amixer."""
    name = "set_volume"
    description = "Set, increase, decrease, or mute system audio volume."
    patterns = [
        r"(?:set\s+)?volume\s+(?:to\s+)?(?P<level>\d+)\s*%",
        r"volume\s+(?:up|increase)(?:\s+by\s+(?P<up_step>\d+)\s*%)?",
        r"volume\s+(?:down|decrease|lower)(?:\s+by\s+(?P<down_step>\d+)\s*%)?",
        r"(?P<mute>mute|unmute)\s+volume",
    ]

    def execute(self, level: int | None = None, up_step: int | None = None, down_step: int | None = None, mute: str | None = None, **kwargs: Any) -> ActionResult:
        try:
            if mute:
                toggle = "1" if mute == "mute" else "0"
                subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", toggle], check=False)
                return ActionResult(success=True, message=f"Volume {mute}d.")

            if level is not None:
                lvl = max(0, min(100, int(level)))
                subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{lvl}%"], check=False)
                return ActionResult(success=True, message=f"Volume set to {lvl} percent.")

            if up_step is not None:
                step = int(up_step)
                subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"+{step}%"], check=False)
                return ActionResult(success=True, message=f"Volume increased by {step} percent.")

            if down_step is not None:
                step = int(down_step)
                subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"-{step}%"], check=False)
                return ActionResult(success=True, message=f"Volume decreased by {step} percent.")

            return ActionResult(success=False, message="Invalid volume parameters.")
        except Exception as err:
            return ActionResult(success=False, message=f"Failed to change volume: {err}")


class SystemStatsAction(BaseAction):
    """Retrieves CPU, RAM, and Battery statistics."""
    name = "system_stats"
    description = "Check CPU usage, memory usage, or battery status."
    patterns = [
        r"\b(?:check\s+)?system\s+(?:status|stats|performance)\b",
        r"\b(?:system\s+status|system\s+stats)\b",
        r"\b(?:check\s+)?(?:battery|power)(?:\s+status|\s+level)?\b",
        r"\b(?:check\s+)?cpu(?:\s+usage)?\b",
        r"\b(?:check\s+)?(?:ram|memory)(?:\s+usage)?\b",
    ]

    def execute(self, **kwargs: Any) -> ActionResult:
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            battery = psutil.sensors_battery()
            
            bat_str = f"Battery at {battery.percent:.0f}%" if battery else "No battery detected"
            msg = f"System status: CPU at {cpu:.0f}%, Memory at {mem:.0f}%, {bat_str}."
            return ActionResult(success=True, message=msg, data={"cpu": cpu, "memory": mem, "battery": battery.percent if battery else None})
        except Exception as err:
            return ActionResult(success=False, message=f"Failed to get system stats: {err}")


class ScreenshotAction(BaseAction):
    """Takes a screenshot of the current desktop."""
    name = "take_screenshot"
    description = "Capture a full screenshot and save to Pictures."
    patterns = [
        r"(?:take\s+a?\s*)?(?:screenshot|screen\s+capture|capture\s+screen)",
    ]

    def execute(self, **kwargs: Any) -> ActionResult:
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            pic_dir = Path.home() / "Pictures" / "Screenshots"
            pic_dir.mkdir(parents=True, exist_ok=True)
            output_file = pic_dir / f"screenshot_{timestamp}.png"

            # Check available screenshot CLI tools
            if shutil.which("scrot"):
                subprocess.run(["scrot", str(output_file)], check=False)
            elif shutil.which("gnome-screenshot"):
                subprocess.run(["gnome-screenshot", "-f", str(output_file)], check=False)
            elif shutil.which("import"):  # ImageMagick
                subprocess.run(["import", "-window", "root", str(output_file)], check=False)
            else:
                return ActionResult(success=False, message="No screenshot utility (scrot/gnome-screenshot) found.")

            return ActionResult(success=True, message=f"Screenshot saved to {output_file.name}.", data={"path": str(output_file)})
        except Exception as err:
            return ActionResult(success=False, message=f"Failed to take screenshot: {err}")


class LockScreenAction(BaseAction):
    """Locks the desktop screen."""
    name = "lock_screen"
    description = "Lock the user session screen."
    patterns = [
        r"lock\s+(?:the\s+)?(?:screen|pc|computer|system)",
    ]

    def execute(self, **kwargs: Any) -> ActionResult:
        try:
            if shutil.which("loginctl"):
                subprocess.run(["loginctl", "lock-session"], check=False)
                return ActionResult(success=True, message="Screen locked.")
            elif shutil.which("xdg-screensaver"):
                subprocess.run(["xdg-screensaver", "lock"], check=False)
                return ActionResult(success=True, message="Screen locked.")
            return ActionResult(success=False, message="Screen locking utility not available.")
        except Exception as err:
            return ActionResult(success=False, message=f"Failed to lock screen: {err}")
