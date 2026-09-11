"""Native Linux Desktop Notification Subsystem for JARVIS PC."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess  # nosec B404
from pathlib import Path

logger = logging.getLogger(__name__)

_NOTIFY_INITTED = False


def _get_icon_path() -> str:
    """Return path to JARVIS desktop icon if it exists."""
    # Check current directory assets
    candidate = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "icons" / "jarvis.png"
    if candidate.exists():
        return str(candidate)

    # Check installed user icon
    user_icon = Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "jarvis.png"
    if user_icon.exists():
        return str(user_icon)

    # Check system installed icon
    sys_icon = Path("/usr/share/icons/hicolor/256x256/apps/jarvis.png")
    if sys_icon.exists():
        return str(sys_icon)

    return "dialog-information"


def notify(
    title: str,
    message: str,
    urgency: str = "normal",
    timeout_ms: int = 5000,
) -> bool:
    """Send a native Linux desktop notification via libnotify or notify-send.

    Args:
        title: Notification header
        message: Notification body text
        urgency: 'low', 'normal', or 'critical'
        timeout_ms: Duration in milliseconds before auto-dismissal
    """
    global _NOTIFY_INITTED
    icon = _get_icon_path()

    # Priority 1: GObject Introspection libnotify (in-process, fastest)
    try:
        import gi
        gi.require_version("Notify", "0.7")
        from gi.repository import Notify

        if not _NOTIFY_INITTED:
            Notify.init("JARVIS")
            _NOTIFY_INITTED = True

        notification = Notify.Notification.new(title, message, icon)
        if urgency == "critical":
            notification.set_urgency(Notify.Urgency.CRITICAL)
        elif urgency == "low":
            notification.set_urgency(Notify.Urgency.LOW)
        else:
            notification.set_urgency(Notify.Urgency.NORMAL)

        notification.set_timeout(timeout_ms)
        notification.show()
        return True
    except Exception as exc:
        logger.debug("GObject Notify failed: %s; falling back to notify-send", exc)

    # Priority 2: notify-send executable
    notify_send = shutil.which("notify-send")
    if notify_send:
        cmd = [notify_send, "-u", urgency, "-t", str(timeout_ms), title, message]
        if icon and os.path.exists(icon):
            cmd.extend(["-i", icon])
        try:
            subprocess.run(cmd, check=False, timeout=3)  # nosec B603
            return True
        except Exception as exc:
            logger.debug("notify-send subprocess failed: %s", exc)

    # Priority 3: Fallback log
    logger.info("[NOTIFICATION] %s: %s", title, message)
    return False
