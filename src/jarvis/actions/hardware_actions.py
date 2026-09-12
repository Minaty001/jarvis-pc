"""Hardware, display brightness, and network actions for Linux."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from typing import Any, Optional

from .base import ActionResult, BaseAction

logger = logging.getLogger("jarvis.actions.hardware")

_cached_display: Optional[str] = None
_current_brightness: float = 0.8  # reasonable default


def get_primary_display() -> Optional[str]:
    """Auto-detect the primary or first connected xrandr display."""
    global _cached_display
    if _cached_display:
        return _cached_display

    if not shutil.which("xrandr"):
        return None

    try:
        out = subprocess.check_output(["xrandr", "--query"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if " connected" in line:
                display_name = line.split()[0]
                _cached_display = display_name
                return display_name
    except Exception as err:
        logger.debug("Failed to detect display via xrandr: %s", err)

    return None


class BrightnessAction(BaseAction):
    """Controls display screen brightness via xrandr."""
    name = "set_brightness"
    description = "Set, increase, or decrease monitor screen brightness."
    patterns = [
        r"(?:set\s+)?brightness\s+(?:to\s+)?(?P<level>\d+)\s*%?",
        r"(?:increase|raise|boost)\s+brightness(?:\s+by\s+(?P<up_step>\d+)\s*%?)?",
        r"(?:decrease|lower|dim)\s+brightness(?:\s+by\s+(?P<down_step>\d+)\s*%?)?",
        r"\b(?:dim|brighten)\s+(?:the\s+)?screen\b",
    ]

    def execute(
        self,
        level: int | str | None = None,
        up_step: int | str | None = None,
        down_step: int | str | None = None,
        **kwargs: Any,
    ) -> ActionResult:
        global _current_brightness
        display = get_primary_display()
        if not display:
            return ActionResult(success=False, message="Could not detect active display output for brightness control.")

        try:
            if level is not None:
                pct = max(10, min(100, int(level)))
                val = pct / 100.0
                subprocess.run(["xrandr", "--output", display, "--brightness", f"{val:.2f}"], check=False)
                _current_brightness = val
                return ActionResult(success=True, message=f"Screen brightness set to {pct} percent.")

            if up_step is not None:
                step = int(up_step) if str(up_step).isdigit() else 15
                new_val = min(1.0, _current_brightness + (step / 100.0))
                subprocess.run(["xrandr", "--output", display, "--brightness", f"{new_val:.2f}"], check=False)
                _current_brightness = new_val
                pct = int(round(new_val * 100))
                return ActionResult(success=True, message=f"Brightness increased to {pct} percent.")

            if down_step is not None:
                step = int(down_step) if str(down_step).isdigit() else 15
                new_val = max(0.1, _current_brightness - (step / 100.0))
                subprocess.run(["xrandr", "--output", display, "--brightness", f"{new_val:.2f}"], check=False)
                _current_brightness = new_val
                pct = int(round(new_val * 100))
                return ActionResult(success=True, message=f"Brightness decreased to {pct} percent.")

            # Default dim/brighten relative toggles
            return ActionResult(success=False, message="Please specify a brightness level percentage.")
        except Exception as err:
            return ActionResult(success=False, message=f"Failed to adjust brightness: {err}")


class WifiStatusAction(BaseAction):
    """Checks network and Wi-Fi connectivity status."""
    name = "wifi_status"
    description = "Check current Wi-Fi network and internet connection state."
    patterns = [
        r"\b(?:check\s+)?(?:wifi|internet|network)(?:\s+status|\s+connection)?\b",
        r"\bwhat\s+wifi\s+am\s+i\s+on\b",
    ]

    def execute(self, **kwargs: Any) -> ActionResult:
        if not shutil.which("nmcli"):
            return ActionResult(success=False, message="nmcli tool is not available.")

        try:
            # Check active Wi-Fi connection
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            for line in out.splitlines():
                if line.startswith("yes:"):
                    ssid = line.split(":", 1)[1].strip()
                    if ssid:
                        return ActionResult(success=True, message=f"Connected to Wi-Fi network {ssid}, boss.")

            # Check general connectivity
            status_out = subprocess.check_output(["nmcli", "general", "status"], text=True, stderr=subprocess.DEVNULL)
            if "connected" in status_out.lower():
                return ActionResult(success=True, message="Network is connected via ethernet or local link, boss.")

            return ActionResult(success=True, message="Wi-Fi is currently disconnected, boss.")
        except Exception as err:
            return ActionResult(success=False, message=f"Could not retrieve network status: {err}")
