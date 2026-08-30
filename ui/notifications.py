"""
Desktop Notifications — plyer-based notifications.
"""

from config.logger import get_logger

logger = get_logger("ui.notifications")

try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False
    logger.warning("plyer not installed. Notifications disabled.")


def notify(title: str, message: str, timeout: int = 5) -> bool:
    """Send a desktop notification."""
    if not HAS_PLYER:
        logger.warning("Notifications unavailable: %s - %s", title, message)
        return False

    try:
        notification.notify(
            title=title,
            message=message[:256],
            timeout=timeout,
        )
        return True
    except Exception as e:
        logger.error("Notification failed: %s", e)
        return False


def notify_jarvis(message: str) -> bool:
    """Send a Jarvis-branded notification."""
    return notify("JARVIS", message)
