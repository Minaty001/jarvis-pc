"""
JarvisApp — the native GTK application.

Wires together:
  * MainWindow     (the main window: orb HUD + chat + panels)
  * FloatingOrb    (always-on-top ambient orb that keeps JARVIS in the background)
  * system tray    (pystray icon; optional)
  * UIBridge       (binds the cognitive engine to the UI)

Launch from run.py with:  from ui.app import launch_ui; launch_ui(engine)
where `engine` is the bundle of cognitive objects (see bridge.UIBridge).
"""

import sys
import threading

from gi.repository import Gtk, GLib

from config.logger import get_logger
from ui.theme import load_css
from ui.main_window import MainWindow
from ui.floating_orb import FloatingOrb
from ui.bridge import UIBridge
from ui.linux_mint import notify

logger = get_logger("ui.app")


class JarvisApp(Gtk.Application):
    def __init__(self, engine=None):
        super().__init__(application_id="com.jarvis.desktop")
        self.engine = engine
        self.bridge = UIBridge(engine)
        self.main_window = None
        self.floating_orb = None
        self.tray = None
        self._started = False

    # ── Gtk.Application vfuncs ─────────────────────────────────────────
    def do_activate(self):
        if self._started:
            # second activate → show window
            if self.main_window:
                self.main_window.present()
            return
        self._started = True
        load_css()

        # Floating orb first (always present, runs in background)
        self.floating_orb = FloatingOrb(
            size=96,
            on_toggle=self._toggle_main,
            on_quit=self._quit,
        )
        self.floating_orb.show_all()

        # Main window (start hidden; user opens via orb or tray)
        self.main_window = MainWindow(
            app=self,
            on_send=self.bridge.send_chat,
            on_hide=self._on_main_hidden,
            on_quit=self._quit,
        )

        # Connect bridge → UI
        self.bridge.on_orb_state = self._on_orb_state
        self.bridge.on_status = self.main_window.set_status
        self.bridge.on_chat = self.main_window.add_chat
        self.bridge.on_system = self.main_window.update_system
        self.bridge.on_tools = self.main_window.set_tools_summary
        self.bridge.on_memory = self.main_window.set_memory_summary
        self.bridge.on_suggestion = self._on_suggestion

        # Start bridge (engine polling + events)
        self.bridge.start()

        # Tray icon (best-effort)
        self._start_tray()

        # Welcome line
        self.main_window.add_chat("system", "JARVIS is online. Click the orb to open this window.")
        self.main_window.set_status("Online")
        notify("JARVIS", "Online — JARVIS is watching in the background.", urgency="low")

        # Auto-show the main window on first launch for visibility
        self.main_window.show_all()
        self.main_window.present()

    # ── callbacks ───────────────────────────────────────────────────────
    def _on_orb_state(self, state):
        if self.main_window:
            self.main_window.set_orb_state(state)
        if self.floating_orb:
            self.floating_orb.set_state(state)

    def _toggle_main(self):
        if self.main_window:
            self.main_window.toggle_visible()
            if self.main_window.get_visible():
                self.main_window.focus_entry()

    def _on_main_hidden(self):
        # ensure floating orb stays visible so JARVIS keeps "watching"
        if self.floating_orb and not self.floating_orb.get_visible():
            self.floating_orb.show_all()

    def _on_suggestion(self, text):
        if self.main_window:
            self.main_window.add_chat("system", f"Suggestion: {text}")
        notify("JARVIS Suggestion", text, urgency="normal")

    def _on_tray_status(self):
        self._toggle_main()

    def _start_tray(self):
        try:
            from ui.tray import JarvisTray
            self.tray = JarvisTray(
                on_status=self._on_tray_status,
                on_settings=self._toggle_main,
                on_quit=self._quit,
            )
            self.tray.start()
        except Exception as e:
            logger.warning("Tray unavailable: %s", e)

    def _quit(self):
        logger.info("JARVIS UI quitting")
        try:
            self.bridge.stop()
        except Exception:
            pass
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        if self.floating_orb:
            self.floating_orb.orb.stop_animation()
        GLib.idle_add(self.quit)

    # ── public entry ────────────────────────────────────────────────────
    def run_app(self):
        logger.info("Launching JARVIS GTK UI")
        return self.run(sys.argv)


def launch_ui(engine) -> threading.Thread:
    """Launch the JARVIS GTK UI on the calling (main) thread and block.

    If you need to run it alongside an already-running asyncio engine, call this
    from the main thread — Gtk.Application owns the main loop. Returns the
    Gtk.Application instance (already running) for advanced callers.
    """
    app = JarvisApp(engine=engine)
    # Gtk.Application.run is blocking; run it on the current thread.
    app.run_app()
    return app
