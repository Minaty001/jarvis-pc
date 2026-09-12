"""Window and desktop workspace management actions for Linux via wmctrl."""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Any

from .base import ActionResult, BaseAction

logger = logging.getLogger("jarvis.actions.window")


class ShowDesktopAction(BaseAction):
    """Minimizes all windows to show desktop."""
    name = "show_desktop"
    description = "Show desktop by minimizing all open windows."
    patterns = [
        r"\bshow\s+desktop\b",
        r"\bminimize\s+all(?:\s+windows)?\b",
    ]

    def execute(self, **kwargs: Any) -> ActionResult:
        if not shutil.which("wmctrl"):
            return ActionResult(success=False, message="wmctrl is not installed.")

        try:
            subprocess.run(["wmctrl", "-k", "on"], check=False)
            return ActionResult(success=True, message="Desktop shown.")
        except Exception as err:
            return ActionResult(success=False, message=f"Failed to show desktop: {err}")


class RestoreWindowsAction(BaseAction):
    """Restores minimized windows back from desktop mode."""
    name = "restore_windows"
    description = "Restore windows back from desktop mode."
    patterns = [
        r"\brestore\s+(?:all\s+)?windows\b",
        r"\bunminimize\s+(?:all\s+)?windows\b",
    ]

    def execute(self, **kwargs: Any) -> ActionResult:
        if not shutil.which("wmctrl"):
            return ActionResult(success=False, message="wmctrl is not installed.")

        try:
            subprocess.run(["wmctrl", "-k", "off"], check=False)
            return ActionResult(success=True, message="Windows restored.")
        except Exception as err:
            return ActionResult(success=False, message=f"Failed to restore windows: {err}")


class FocusWindowAction(BaseAction):
    """Focuses or switches to an open application window."""
    name = "focus_window"
    description = "Focus or switch to an open application window."
    patterns = [
        r"\b(?:focus|switch\s+to)\s+(?P<app_name>[a-zA-Z0-9\-_]+)\b",
    ]

    def execute(self, app_name: str | None = None, **kwargs: Any) -> ActionResult:
        if not shutil.which("wmctrl"):
            return ActionResult(success=False, message="wmctrl is not installed.")

        if not app_name:
            return ActionResult(success=False, message="Please specify an application to focus.")

        try:
            clean_name = app_name.strip()
            subprocess.run(["wmctrl", "-a", clean_name], check=False)
            return ActionResult(success=True, message=f"Focused window {clean_name}.")
        except Exception as err:
            return ActionResult(success=False, message=f"Failed to focus window: {err}")
