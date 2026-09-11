"""JARVIS Floating Orb — Frameless, Draggable, Always-on-top Desktop Widget."""

from __future__ import annotations

import logging
from typing import Callable, Optional

try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gtk, Gdk
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False
    Gtk = object  # type: ignore

from jarvis.ui.orb import OrbWidget

logger = logging.getLogger(__name__)


class FloatingOrb(Gtk.Window if GTK_AVAILABLE else object):  # type: ignore
    """Ambient floating widget that stays on top and allows quick interaction."""

    def __init__(
        self,
        size: int = 96,
        on_toggle: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
    ):
        if not GTK_AVAILABLE:
            raise RuntimeError("GTK 3.0 is not available.")
        super().__init__(type=Gtk.WindowType.TOPLEVEL)

        self.on_toggle = on_toggle
        self.on_quit = on_quit
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._win_start_x = 0
        self._win_start_y = 0
        self._dragging = False

        self.set_title("JARVIS")
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_app_paintable(True)

        # Transparent window support
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        self.orb = OrbWidget(size=size, state="idle")
        self.add(self.orb)

        # Position at bottom-right of primary monitor
        self._position_default(size)

        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.connect("button-press-event", self._on_button_press)
        self.connect("button-release-event", self._on_button_release)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("draw", self._on_window_draw)

    def set_state(self, state: str) -> None:
        self.orb.set_state(state)

    def _position_default(self, size: int) -> None:
        try:
            display = Gdk.Display.get_default()
            monitor = display.get_primary_monitor() if display else None
            if monitor:
                geom = monitor.get_geometry()
                x = geom.x + geom.width - size - 24
                y = geom.y + geom.height - size - 60
                self.move(x, y)
        except Exception as exc:
            logger.debug("Could not determine primary monitor position: %s", exc)

    def _on_window_draw(self, _widget, cr) -> bool:
        # Clear background to transparent
        cr.set_source_rgba(0, 0, 0, 0)
        cr.set_operator(0)  # CLEAR
        cr.paint()
        cr.set_operator(2)  # OVER
        return False

    def _on_button_press(self, _widget, event: Gdk.EventButton) -> bool:
        if event.button == 1:  # Left click
            self._drag_start_x = int(event.x_root)
            self._drag_start_y = int(event.y_root)
            pos = self.get_position()
            self._win_start_x = pos[0]
            self._win_start_y = pos[1]
            self._dragging = False
            return True
        elif event.button == 3:  # Right click
            self._show_context_menu(event)
            return True
        return False

    def _on_motion(self, _widget, event: Gdk.EventMotion) -> bool:
        if event.state & Gdk.ModifierType.BUTTON1_MASK:
            dx = int(event.x_root) - self._drag_start_x
            dy = int(event.y_root) - self._drag_start_y
            if abs(dx) > 4 or abs(dy) > 4:
                self._dragging = True
                self.move(self._win_start_x + dx, self._win_start_y + dy)
            return True
        return False

    def _on_button_release(self, _widget, event: Gdk.EventButton) -> bool:
        if event.button == 1:
            if not self._dragging and self.on_toggle:
                self.on_toggle()
            self._dragging = False
            return True
        return False

    def _show_context_menu(self, event: Gdk.EventButton) -> None:
        menu = Gtk.Menu()

        item_toggle = Gtk.MenuItem(label="Open / Close HUD")
        item_toggle.connect("activate", lambda _: self.on_toggle() if self.on_toggle else None)
        menu.append(item_toggle)

        item_sep = Gtk.SeparatorMenuItem()
        menu.append(item_sep)

        item_quit = Gtk.MenuItem(label="Exit JARVIS")
        item_quit.connect("activate", lambda _: self.on_quit() if self.on_quit else Gtk.main_quit())
        menu.append(item_quit)

        menu.show_all()
        menu.popup_at_pointer(event)
