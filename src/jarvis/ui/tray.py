"""
Native desktop system tray indicator for Linux Mint (AyatanaAppIndicator3 / Gtk.StatusIcon).
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

APPINDICATOR_AVAILABLE = False
AppIndicator = None

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    try:
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as AppIndicator
        APPINDICATOR_AVAILABLE = True
    except (ImportError, ValueError):
        try:
            gi.require_version("AppIndicator3", "0.1")
            from gi.repository import AppIndicator3 as AppIndicator
            APPINDICATOR_AVAILABLE = True
        except (ImportError, ValueError):
            APPINDICATOR_AVAILABLE = False
except Exception as exc:
    logger.debug("GTK or AppIndicator not available: %s", exc)
    Gtk = object  # type: ignore


class JarvisTray:
    """Desktop system tray indicator with status, quick toggles, and quit actions."""

    def __init__(
        self,
        on_toggle_window: Callable[[], None],
        on_toggle_orb: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self.on_toggle_window = on_toggle_window
        self.on_toggle_orb = on_toggle_orb
        self.on_quit = on_quit

        self.indicator: Optional[object] = None
        self.status_icon: Optional[object] = None
        self._init_tray()

    def _init_tray(self) -> None:
        if APPINDICATOR_AVAILABLE and AppIndicator:
            try:
                self.indicator = AppIndicator.Indicator.new(
                    "jarvis-pc-tray",
                    "utilities-terminal",
                    AppIndicator.IndicatorCategory.APPLICATION_STATUS,
                )
                self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
                menu = self._build_menu()
                self.indicator.set_menu(menu)
                logger.info("System tray initialized via AyatanaAppIndicator3.")
                return
            except Exception as exc:
                logger.warning("Failed to initialize AyatanaAppIndicator3: %s", exc)

        # Fallback to Gtk.StatusIcon
        try:
            if hasattr(Gtk, "StatusIcon"):
                self.status_icon = Gtk.StatusIcon.new_from_icon_name("utilities-terminal")
                self.status_icon.set_title("JARVIS PC")
                self.status_icon.set_tooltip_text("JARVIS PC — Assistant Online")
                self.status_icon.connect("activate", lambda _icon: self.on_toggle_window())
                self.status_icon.connect("popup-menu", self._on_status_icon_popup)
                logger.info("System tray initialized via Gtk.StatusIcon fallback.")
        except Exception as exc:
            logger.warning("Failed to initialize Gtk.StatusIcon fallback: %s", exc)

    def _build_menu(self) -> Gtk.Menu:
        menu = Gtk.Menu()

        # Header Title
        title_item = Gtk.MenuItem(label="JARVIS PC — Assistant Online")
        title_item.set_sensitive(False)
        menu.append(title_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Toggle Main Dashboard
        toggle_win_item = Gtk.MenuItem(label="Toggle Dashboard")
        toggle_win_item.connect("activate", lambda _widget: self.on_toggle_window())
        menu.append(toggle_win_item)

        # Toggle Floating ORB
        toggle_orb_item = Gtk.MenuItem(label="Toggle Floating ORB")
        toggle_orb_item.connect("activate", lambda _widget: self.on_toggle_orb())
        menu.append(toggle_orb_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Quit item
        quit_item = Gtk.MenuItem(label="Quit JARVIS")
        quit_item.connect("activate", lambda _widget: self.on_quit())
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _on_status_icon_popup(self, _icon: object, button: int, activate_time: int) -> None:
        menu = self._build_menu()
        menu.popup(None, None, None, None, button, activate_time)

    def destroy(self) -> None:
        """Clean up tray icon and indicators."""
        if self.indicator:
            try:
                self.indicator.set_status(AppIndicator.IndicatorStatus.PASSIVE)
            except Exception as exc:
                logger.debug("Failed to set indicator status to PASSIVE: %s", exc)
        if self.status_icon:
            try:
                self.status_icon.set_visible(False)
            except Exception as exc:
                logger.debug("Failed to hide status icon: %s", exc)
