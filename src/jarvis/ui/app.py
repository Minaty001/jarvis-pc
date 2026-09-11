"""JARVIS Desktop Application — Native GTK3 Application Coordinator."""

from __future__ import annotations

import logging
import sys
from typing import Optional

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, GLib
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False
    Gtk = object  # type: ignore

from jarvis.ui.theme import load_css
from jarvis.ui.floating_orb import FloatingOrb
from jarvis.ui.main_window import MainWindow
from jarvis.ui.bridge import UIBridge
from jarvis.ui.tray import JarvisTray
from jarvis.ui.hotkey import GlobalHotkeyManager

logger = logging.getLogger(__name__)


class JarvisApp(Gtk.Application if GTK_AVAILABLE else object):  # type: ignore
    """GTK Application managing the Floating Orb, HUD Main Window, and Core Bridge."""

    def __init__(self, app_core=None):
        if not GTK_AVAILABLE:
            raise RuntimeError("GTK 3.0 is not available on this system.")
        super().__init__(application_id="com.jarvis.desktop")
        self.app_core = app_core
        self.bridge = UIBridge(app_core)
        self.main_window: Optional[MainWindow] = None
        self.floating_orb: Optional[FloatingOrb] = None
        self.tray: Optional[JarvisTray] = None
        self.hotkeys: Optional[GlobalHotkeyManager] = None
        self._activated = False

    def do_activate(self) -> None:
        if self._activated:
            if self.main_window:
                self.main_window.present()
            return

        self._activated = True
        load_css()

        # 1. Floating Orb (always present ambient widget)
        self.floating_orb = FloatingOrb(
            size=96,
            on_toggle=self._toggle_main_window,
            on_quit=self._quit_application,
        )
        self.add_window(self.floating_orb)
        self.floating_orb.show_all()

        # 2. Main HUD Dashboard Window
        self.main_window = MainWindow(
            app=self,
            on_send=self.bridge.send_chat,
            on_hide=self._on_main_hidden,
            on_quit=self._quit_application,
        )
        self.add_window(self.main_window)
        self.main_window.show_all()
        self.main_window.present()

        # 3. Wire Bridge hooks to UI
        self.bridge.on_orb_state = self._on_orb_state
        self.bridge.on_status = self.main_window.set_status
        self.bridge.on_chat = self.main_window.add_chat
        self.bridge.on_system = self.main_window.update_system
        self.bridge.on_tools = self.main_window.set_tools_summary
        self.bridge.on_memory = self.main_window.set_memory_summary

        # 4. Start Core Bridge
        self.bridge.start()

        # 5. System Tray & Global Hotkeys (Linux Mint / Cinnamon desktop integration)
        self.tray = JarvisTray(
            on_toggle_window=self._toggle_main_window,
            on_toggle_orb=self._toggle_floating_orb,
            on_quit=self._quit_application,
        )
        self.hotkeys = GlobalHotkeyManager()
        self.hotkeys.bind("<Super>space", self._toggle_main_window)
        self.hotkeys.bind("<Ctrl><Alt>j", self._toggle_main_window)

        # Welcome message
        self.main_window.add_chat("assistant", "Greetings! JARVIS PC is online and ready to assist you.")

    def _on_orb_state(self, state: str) -> None:
        if self.floating_orb:
            self.floating_orb.set_state(state)
        if self.main_window:
            self.main_window.set_orb_state(state)

    def _toggle_main_window(self) -> None:
        if not self.main_window:
            return
        if self.main_window.is_visible():
            self.main_window.hide()
        else:
            self.main_window.present()

    def _toggle_floating_orb(self) -> None:
        if not self.floating_orb:
            return
        if self.floating_orb.is_visible():
            self.floating_orb.hide()
        else:
            self.floating_orb.show_all()

    def _on_main_hidden(self) -> None:
        logger.debug("Main window hidden; JARVIS continues running via Floating Orb.")

    def _quit_application(self) -> None:
        logger.info("Quitting JARVIS application...")
        if self.hotkeys:
            self.hotkeys.unbind()
        if self.tray:
            self.tray.destroy()
        if self.bridge:
            self.bridge.stop()
        self.quit()


def launch_ui(app_core=None) -> int:
    """Entrypoint to launch the GTK3 JARVIS desktop application."""
    if not GTK_AVAILABLE:
        logger.error("Cannot launch UI: GTK 3.0 or PyGObject is not installed.")
        return 1

    app = JarvisApp(app_core=app_core)
    # Filter arguments so Gtk.Application doesn't parse CLI subcommands as files
    clean_argv = [sys.argv[0]]
    return app.run(clean_argv)
