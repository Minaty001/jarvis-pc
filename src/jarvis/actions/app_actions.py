"""Application management actions: Open and Close desktop applications."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict

import psutil
from .base import ActionResult, BaseAction

# Common app name aliases to system binaries
APP_ALIASES: Dict[str, str] = {
    "chrome": "google-chrome",
    "google chrome": "google-chrome",
    "chromium": "chromium",
    "firefox": "firefox",
    "browser": "x-www-browser",
    "terminal": "x-terminal-emulator",
    "code": "code",
    "vs code": "code",
    "vscode": "code",
    "calculator": "gnome-calculator",
    "calc": "gnome-calculator",
    "files": "nautilus",
    "file manager": "nautilus",
    "settings": "gnome-control-center",
    "spotify": "spotify",
    "text editor": "gedit",
    "editor": "gedit",
}


class OpenAppAction(BaseAction):
    """Opens a desktop application."""
    name = "open_app"
    description = "Launch a desktop application (e.g. Chrome, Terminal, VS Code, Calculator, Files)."
    patterns = [
        r"(?:open|launch|start)\s+(?:the\s+)?(?P<app>[a-zA-Z0-9_\-\s]+)",
    ]

    def execute(self, app: str = "", **kwargs: Any) -> ActionResult:
        app_clean = app.strip().lower()
        if not app_clean:
            return ActionResult(success=False, message="No application specified.")

        binary = APP_ALIASES.get(app_clean, app_clean)
        
        # Check if binary exists or fall back to xdg-open
        executable = shutil.which(binary)
        if not executable:
            # Try searching for matching desktop commands
            if shutil.which(app_clean):
                executable = shutil.which(app_clean)
            elif shutil.which(f"gnome-{app_clean}"):
                executable = shutil.which(f"gnome-{app_clean}")

        if not executable:
            return ActionResult(success=False, message=f"Application '{app_clean}' not found on system.")

        try:
            subprocess.Popen(
                [executable],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            return ActionResult(success=True, message=f"Opened {app_clean}.", data={"app": app_clean, "binary": executable})
        except Exception as err:
            return ActionResult(success=False, message=f"Failed to open {app_clean}: {err}")


class CloseAppAction(BaseAction):
    """Closes a running desktop application."""
    name = "close_app"
    description = "Close or terminate a running application."
    patterns = [
        r"(?:close|kill|quit|exit)\s+(?:the\s+)?(?P<app>[a-zA-Z0-9_\-\s]+)",
    ]

    def execute(self, app: str = "", **kwargs: Any) -> ActionResult:
        app_clean = app.strip().lower()
        if not app_clean:
            return ActionResult(success=False, message="No application specified.")

        binary = APP_ALIASES.get(app_clean, app_clean)
        closed_count = 0

        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                proc_name = proc.info.get("name", "").lower()
                cmdline = " ".join(proc.info.get("cmdline") or []).lower()

                if binary in proc_name or app_clean in proc_name or binary in cmdline:
                    proc.terminate()
                    closed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if closed_count > 0:
            return ActionResult(success=True, message=f"Closed {app_clean} ({closed_count} process{'es' if closed_count > 1 else ''}).")
        return ActionResult(success=False, message=f"No running instance of '{app_clean}' found.")
