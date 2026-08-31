"""
Floating Orb — the always-on-top ambient JARVIS presence.

This is the "background watching" window: a small (default 96px) circular orb that
stays above all other windows, can be dragged anywhere, and:
  * single-click  → toggle the main JARVIS window (show/hide)
  * right-click   → context menu (Show, Mute toggle placeholder, Quit)
  * double-click  → focus the command entry in the main window (convenience)

It is a borderless, transparent GTK window. It keeps running even when the main
window is hidden, so JARVIS "keeps watching" in the background.
"""

import os

from gi.repository import Gtk, Gdk, GLib

from ui.orb import OrbWidget
from ui.theme import PALETTE


class FloatingOrb(Gtk.Window):
    def __init__(self, size: int = 96, on_toggle=None, on_quit=None):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self._on_toggle = on_toggle
        self._on_quit = on_quit
        self._size = size
        self._drag_offset = None
        self._down_pos = None
        self._moved = False

        self.set_default_size(size, size)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self._keep_above = True
        self.set_resizable(False)
        # transparent background
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.set_app_paintable(True)
        self.set_name("floating-orb")

        self.orb = OrbWidget(size=size - 8, state="idle")
        self.orb.set_label("")
        self.add(self.orb)

        # position: bottom-right by default
        self.set_position(Gtk.WindowPosition.CENTER)
        GLib.timeout_add(50, self._place_bottom_right)

        # input handling
        self.connect("button-press-event", self._on_press)
        self.connect("button-release-event", self._on_release)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("destroy", self._on_destroy)
        # right-click menu
        self.connect("popup-menu", self._on_popup_menu)

        # tooltip-like label
        self.set_tooltip_text("JARVIS — click to open, drag to move, right-click for menu")

    def _place_bottom_right(self):
        try:
            sw = Gdk.Screen.width()
            sh = Gdk.Screen.height()
            self.move(sw - self._size - 24, sh - self._size - 24)
        except Exception:
            pass
        return False

    # ── public ──────────────────────────────────────────────────────────
    def set_state(self, state: str):
        self.orb.set_state(state)

    def set_label(self, text: str):
        self.orb.set_label(text)

    def toggle(self):
        if self._on_toggle:
            self._on_toggle()

    # ── drag / click ───────────────────────────────────────────────────
    def _on_press(self, widget, event):
        if event.button == 1:
            self._down_pos = (event.x_root, event.y_root)
            self._moved = False
            self._drag_offset = (event.x_root - self.get_position()[0],
                                 event.y_root - self.get_position()[1])
        elif event.button == 3:
            self._show_menu(event)
        return False

    def _on_release(self, widget, event):
        if event.button == 1 and not self._moved:
            # treat as a click → toggle main window
            self.toggle()
        self._drag_offset = None
        self._down_pos = None
        return False

    def _on_motion(self, widget, event):
        if self._drag_offset is not None and self._down_pos is not None:
            dx = event.x_root - self._down_pos[0]
            dy = event.y_root - self._down_pos[1]
            if (dx * dx + dy * dy) > 25:  # moved > 5px → it's a drag
                self._moved = True
            nx = int(event.x_root - self._drag_offset[0])
            ny = int(event.y_root - self._drag_offset[1])
            self.move(max(0, nx), max(0, ny))
        return False

    def _on_destroy(self, widget):
        pass

    # ── right-click menu ────────────────────────────────────────────────
    def _show_menu(self, event):
        menu = Gtk.Menu()
        item_show = Gtk.MenuItem(label="Open JARVIS")
        item_show.connect("activate", lambda *_: self.toggle())
        menu.append(item_show)

        item_hide = Gtk.MenuItem(label="Hide window")
        item_hide.connect("activate", lambda *_: self.toggle())
        menu.append(item_hide)

        sep = Gtk.SeparatorMenuItem()
        menu.append(sep)

        item_quit = Gtk.MenuItem(label="Quit JARVIS")
        item_quit.connect("activate", lambda *_: self._on_quit() if self._on_quit else self.destroy())
        menu.append(item_quit)

        menu.show_all()
        menu.popup_at_pointer(event)

    def _on_popup_menu(self, widget, event):
        self._show_menu(event)
        return True

    @classmethod
    def _restore_method(cls):
        # placeholder for future preference persistence (last position)
        pass
