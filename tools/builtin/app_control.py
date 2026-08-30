"""App Control — Open and close applications on Linux."""

import subprocess
import signal
from typing import Any

from config.logger import get_logger

logger = get_logger("tools.app_control")

# Common app name to binary mapping
APP_MAP = {
    "vscode": "code", "visual studio code": "code", "code": "code",
    "firefox": "firefox", "chrome": "google-chrome", "chromium": "chromium",
    "terminal": "gnome-terminal", "konsole": "konsole",
    "nautilus": "nautilus", "files": "nautilus", "thunar": "thunar",
    "spotify": "spotify", "vlc": "vlc", "mpv": "mpv",
    "gimp": "gimp", "blender": "blender",
    "slack": "slack", "discord": "discord", "telegram": "telegram-desktop",
    "libreoffice": "libreoffice", "calc": "libreoffice --calc",
    "settings": "gnome-control-center", "network": "nm-connection-editor",
    "htop": "gnome-terminal -- htop", "btop": "gnome-terminal -- btop",
    "obsidian": "obsidian", "notion": "notion-app",
}


def open_app(app_name: str) -> dict[str, Any]:
    """Open an application by name."""
    name_lower = app_name.lower().strip()
    binary = APP_MAP.get(name_lower, name_lower)

    try:
        subprocess.Popen(
            binary.split(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        msg = f"Opening {app_name}"
        logger.info(msg)
        return {"success": True, "result": msg}
    except FileNotFoundError:
        msg = f"Application '{app_name}' not found"
        logger.warning(msg)
        return {"success": False, "error": msg, "result": msg}
    except Exception as e:
        msg = f"Failed to open {app_name}: {e}"
        logger.error(msg)
        return {"success": False, "error": str(e), "result": msg}


def close_app(app_name: str) -> dict[str, Any]:
    """Close an application by name."""
    name_lower = app_name.lower().strip()
    binary = APP_MAP.get(name_lower, name_lower).split()[0]

    try:
        result = subprocess.run(
            ["pkill", "-f", binary],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            msg = f"Closed {app_name}"
            logger.info(msg)
            return {"success": True, "result": msg}
        else:
            msg = f"{app_name} was not running"
            return {"success": True, "result": msg}
    except Exception as e:
        msg = f"Failed to close {app_name}: {e}"
        logger.error(msg)
        return {"success": False, "error": str(e), "result": msg}
