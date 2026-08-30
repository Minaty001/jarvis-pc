"""
System Tray — pystray icon with context menu.
"""

import threading
from typing import Callable, Optional

from config.logger import get_logger

logger = get_logger("ui.tray")

try:
    import pystray
    from pystray import MenuItem
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False
    logger.warning("pystray not installed. System tray disabled.")

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def _create_icon_image(color: str = "#00FF00") -> "Image.Image":
    """Create a simple colored circle icon."""
    if not HAS_PIL:
        return None
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    draw.ellipse([8, 8, 56, 56], fill=(r, g, b, 255))
    return img


class JarvisTray:
    """System tray icon for Jarvis."""

    def __init__(
        self,
        on_status: Optional[Callable] = None,
        on_settings: Optional[Callable] = None,
        on_quit: Optional[Callable] = None,
    ):
        self._tray = None
        self._on_status = on_status
        self._on_settings = on_settings
        self._on_quit = on_quit
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the system tray icon."""
        if not HAS_TRAY:
            logger.warning("System tray unavailable")
            return

        menu = pystray.Menu(
            MenuItem("JARVIS Status", self._handle_status, default=True),
            MenuItem("Settings", self._handle_settings),
            pystray.Menu.SEPARATOR,
            MenuItem("Quit", self._handle_quit),
        )

        icon_image = _create_icon_image("#00FF00")
        self._tray = pystray.Icon(
            "jarvis",
            icon=icon_image,
            title="JARVIS PC",
            menu=menu,
        )

        self._thread = threading.Thread(target=self._tray.run, daemon=True)
        self._thread.start()
        logger.info("System tray icon started")

    def update_status(self, status: str, color: str = "#00FF00") -> None:
        """Update tray icon color and tooltip."""
        if self._tray:
            self._tray.title = f"JARVIS: {status}"
            if HAS_PIL:
                self._tray.icon = _create_icon_image(color)

    def stop(self) -> None:
        """Stop the system tray icon."""
        if self._tray:
            self._tray.stop()
            logger.info("System tray icon stopped")

    def _handle_status(self, icon, item):
        if self._on_status:
            self._on_status()

    def _handle_settings(self, icon, item):
        if self._on_settings:
            self._on_settings()

    def _handle_quit(self, icon, item):
        if self._on_quit:
            self._on_quit()
        icon.stop()
