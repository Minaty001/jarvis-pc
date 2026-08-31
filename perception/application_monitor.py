"""
Application Monitor — Tracks running applications, window focus, and desktop state.
Publishes application/window events to the event bus.
"""

import asyncio
import subprocess
import time
from typing import Optional

from config.logger import get_logger
from perception.event_bus import event_bus
from perception.event_models import Event, EventType, EventSeverity, make_event

logger = get_logger("perception.app_monitor")

# Common app name normalizations
APP_ALIASES = {
    "firefox": "Firefox",
    "google-chrome": "Chrome",
    "chromium": "Chromium",
    "code": "VS Code",
    "code-oss": "VS Code",
    "utilus": "LibreOffice",
    "soffice": "LibreOffice",
    "thunar": "Thunar",
    "nautilus": "Files",
    "dolphin": "Dolphin",
    "konsole": "Konsole",
    "alacritty": "Alacritty",
    "kitty": "Kitty",
    "foot": "Foot",
    "终端": "Terminal",
    "gnome-terminal": "Terminal",
    "xfce4-terminal": "Terminal",
}


def _run_xdotool(*args: str) -> str:
    """Run xdotool and return output."""
    try:
        result = subprocess.run(
            ["xdotool"] + list(args),
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _run_wmctrl(*args: str) -> str:
    """Run wmctrl and return output."""
    try:
        result = subprocess.run(
            ["wmctrl"] + list(args),
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _normalize_app_name(name: str) -> str:
    """Normalize application name."""
    if not name:
        return "Unknown"
    base = name.split("/")[-1].split(" ")[0]
    return APP_ALIASES.get(base.lower(), name)


class ApplicationMonitor:
    """Monitors running applications and window focus changes."""

    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_focused_window: str = ""
        self._last_focused_app: str = ""
        self._running_apps: list[str] = []
        self._window_history: list[dict] = []

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Application monitor started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Application monitor stopped")

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                await self._check_focus()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("App monitor error: %s", e)
                await asyncio.sleep(self.poll_interval)

    async def _check_focus(self) -> None:
        """Check current window focus and emit events on change."""
        # Run single xdotool command to get both window ID and name in 1 subprocess call
        window_name = _run_xdotool("getactivewindow", "getwindowname")
        if not window_name:
            return

        app_name = _normalize_app_name(window_name)

        # Detect focus change
        if window_name != self._last_focused_window:
            old_app = self._last_focused_app

            # Publish window focus event
            await event_bus.publish(make_event(
                EventType.WINDOW, "app_monitor",
                {
                    "window_name": window_name,
                    "app_name": app_name,
                    "previous_app": old_app,
                },
                EventSeverity.INFO,
            ))

            # Track history
            self._window_history.append({
                "time": time.time(),
                "app": app_name,
                "window": window_name,
            })
            if len(self._window_history) > 100:
                self._window_history = self._window_history[-100:]

            self._last_focused_window = window_name

            # Publish app event if app changed (check before updating)
            if app_name != self._last_focused_app:
                await event_bus.publish(make_event(
                    EventType.APPLICATION, "app_monitor",
                    {
                        "app_name": app_name,
                        "event": "focus_changed",
                    },
                    EventSeverity.INFO,
                ))

            self._last_focused_app = app_name

    def get_running_apps(self) -> list[str]:
        """Get list of running application names."""
        try:
            output = subprocess.run(
                ["wmctrl", "-l"],
                capture_output=True, text=True, timeout=5,
            )
            apps = []
            for line in output.stdout.strip().split("\n"):
                if line:
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        apps.append(_normalize_app_name(parts[3]))
            return list(set(apps))
        except Exception:
            return []

    def get_focused_window(self) -> dict:
        """Get info about the currently focused window."""
        window_id = _run_xdotool("getactivewindow")
        window_name = _run_xdotool("getwindowname", window_id) if window_id else ""
        return {
            "window_id": window_id,
            "window_name": window_name,
            "app_name": _normalize_app_name(window_name),
        }

    def get_window_history(self, limit: int = 20) -> list[dict]:
        """Get recent window focus history."""
        return self._window_history[-limit:]

    def get_summary(self) -> str:
        focused = self.get_focused_window()
        apps = self.get_running_apps()
        return (
            f"Focused: {focused['app_name']} ({focused['window_name'][:50]}) | "
            f"Running: {len(apps)} apps"
        )


app_monitor = ApplicationMonitor()
