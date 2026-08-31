"""
Linux Mint integration helpers — native desktop notifications + autostart.

Uses libnotify (gi.repository.Notify) so popups look exactly like other Mint
notifications. Falls back gracefully if libnotify isn't available.
"""

from config.logger import get_logger

logger = get_logger("ui.linux_mint")

try:
    import gi
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify
    _initialized = False

    def _ensure_init():
        global _initialized
        if not _initialized:
            Notify.init("JARVIS")
            _initialized = True

    HAS_NOTIFY = True
except Exception as e:  # pragma: no cover
    HAS_NOTIFY = False
    logger.warning("libnotify unavailable: %s", e)


def notify(title: str, message: str, urgency: str = "normal") -> bool:
    """Show a native Linux Mint notification. urgency: low|normal|critical."""
    if not HAS_NOTIFY:
        logger.info("notify[fallback] %s: %s", title, message)
        return False
    try:
        _ensure_init()
        u = getattr(Notify.Urgency, urgency.upper(), Notify.Urgency.NORMAL)
        n = Notify.Notification.new(title, message, "dialog-information")
        n.set_urgency(u)
        n.show()
        return True
    except Exception as e:
        logger.error("notify failed: %s", e)
        return False


def install_autostart() -> str:
    """Install ~/.config/autostart/jarvis.desktop so JARVIS floats at login.

    Returns the path written (or existing). Safe: only writes if missing.
    """
    import os
    from pathlib import Path

    autostart_dir = Path.home() / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    desktop = autostart_dir / "jarvis.desktop"
    if desktop.exists():
        return str(desktop)
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=JARVIS\n"
        "Comment=Personal AI Assistant for Linux Mint\n"
        "Exec=jarvis-ui\n"
        "Icon=jarvis\n"
        "Terminal=false\n"
        "Hidden=false\n"
        "X-GNOME-Autostart-enabled=true\n"
        "X-GNOME-Autostart-Delay=5\n"
        "Categories=Utility;\n"
    )
    desktop.write_text(content)
    try:
        os.chmod(desktop, 0o644)
    except OSError:
        pass
    return str(desktop)
