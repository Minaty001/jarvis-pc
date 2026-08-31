"""
JARVIS MainWindow — the main desktop window.

Layout (Cinnamon-native, dark JARVIS theme):
  ┌─────────────────────────────┬────────────────────┐
  │  ORB HUD (centerpiece)       │  System status      │
  │  status label                │  Active tools       │
  ├─────────────────────────────┤  Memory summary     │
  │  Chat (scroll)               │                     │
  │  [ entry ............ ] Send │                     │
  └─────────────────────────────┴────────────────────┘

The window only renders + exposes setters; all logic lives in the UIBridge / engine.
Closing the window (X) hides it (keeps JARVIS running in the background via the orb).
"""

import datetime

from gi.repository import Gtk, Gdk, GLib, Pango

from ui.orb import OrbWidget
from ui.theme import PALETTE, ORB_STATES


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app=None, on_send=None, on_hide=None, on_quit=None):
        super().__init__(application=app, title="JARVIS")
        self._on_send = on_send
        self._on_hide = on_hide
        self._on_quit = on_quit
        self.set_default_size(900, 620)
        self.set_border_width(0)

        # ── header ──
        hdr = Gtk.HeaderBar()
        hdr.set_show_close_button(True)
        hdr.set_title("JARVIS")
        hdr.set_subtitle("Personal AI Assistant")
        self._status_lbl = Gtk.Label(label="Initializing…")
        self._status_lbl.get_style_context().add_class("subtle")
        hdr.pack_start(self._status_lbl)

        self._hide_btn = Gtk.Button(label="Minimize")
        self._hide_btn.connect("clicked", lambda *_: self._do_hide())
        hdr.pack_end(self._hide_btn)
        self.set_titlebar(hdr)

        # ── body paned ──
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(620)

        # left column
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        left.set_border_width(12)

        # ORB HUD
        orb_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        orb_frame.set_name("orb-frame")
        orb_frame.set_border_width(12)
        self.orb = OrbWidget(size=170, state="idle")
        self._orb_caption = Gtk.Label(label="JARVIS ONLINE")
        self._orb_caption.get_style_context().add_class("accent")
        orb_frame.pack_start(self.orb, False, False, 0)
        orb_frame.pack_start(self._orb_caption, False, False, 0)
        left.pack_start(orb_frame, False, False, 0)

        # chat
        chat_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        chat_frame.get_style_context().add_class("jarvis-surface")
        chat_frame.set_border_width(8)
        chat_label = Gtk.Label(label="Conversation")
        chat_label.get_style_context().add_class("title")
        chat_label.set_halign(Gtk.Align.START)
        chat_frame.pack_start(chat_label, False, False, 0)

        self._chat_list = Gtk.ListBox()
        self._chat_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._chat_list.get_style_context().add_class("chat-scroll")
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(220)
        scrolled.add(self._chat_list)
        chat_frame.pack_start(scrolled, True, True, 0)

        # input row
        input_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._entry = Gtk.Entry()
        self._entry.set_placeholder_text("Talk to JARVIS…  (Enter to send)")
        self._entry.connect("activate", self._on_entry_activate)
        send_btn = Gtk.Button(label="Send")
        send_btn.get_style_context().add_class("suggested-action")
        send_btn.connect("clicked", self._on_send_clicked)
        input_row.pack_start(self._entry, True, True, 0)
        input_row.pack_start(send_btn, False, False, 0)
        chat_frame.pack_start(input_row, False, False, 0)

        left.pack_start(chat_frame, True, True, 0)
        paned.pack1(left, True, False)

        # right column
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right.set_border_width(12)

        # System panel
        sys_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sys_frame.get_style_context().add_class("jarvis-surface")
        sys_frame.set_border_width(8)
        t = Gtk.Label(label="System")
        t.get_style_context().add_class("title")
        t.set_halign(Gtk.Align.START)
        sys_frame.pack_start(t, False, False, 0)
        self._sys_grid = Gtk.Grid()
        self._sys_grid.set_column_spacing(8)
        self._sys_grid.set_row_spacing(4)
        sys_frame.pack_start(self._sys_grid, False, False, 0)
        self._sys_vals = {}
        self._build_sys_rows()
        right.pack_start(sys_frame, False, False, 0)

        # Tools panel
        tools_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        tools_frame.get_style_context().add_class("jarvis-surface")
        tools_frame.set_border_width(8)
        tt = Gtk.Label(label="Tools")
        tt.get_style_context().add_class("title")
        tt.set_halign(Gtk.Align.START)
        tools_frame.pack_start(tt, False, False, 0)
        self._tools_lbl = Gtk.Label(label="—")
        self._tools_lbl.set_halign(Gtk.Align.START)
        self._tools_lbl.set_line_wrap(True)
        self._tools_lbl.get_style_context().add_class("subtle")
        tools_frame.pack_start(self._tools_lbl, False, False, 0)
        right.pack_start(tools_frame, False, False, 0)

        # Memory panel
        mem_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        mem_frame.get_style_context().add_class("jarvis-surface")
        mem_frame.set_border_width(8)
        mt = Gtk.Label(label="Memory")
        mt.get_style_context().add_class("title")
        mt.set_halign(Gtk.Align.START)
        mem_frame.pack_start(mt, False, False, 0)
        self._mem_lbl = Gtk.Label(label="—")
        self._mem_lbl.set_halign(Gtk.Align.START)
        self._mem_lbl.set_line_wrap(True)
        self._mem_lbl.get_style_context().add_class("subtle")
        mem_frame.pack_start(self._mem_lbl, False, False, 0)
        right.pack_start(mem_frame, False, False, 0)

        paned.pack2(right, False, False)
        self.add(paned)

        self.connect("delete-event", self._on_delete)

    # ── builders ────────────────────────────────────────────────────────
    def _build_sys_rows(self):
        rows = [
            ("CPU", "cpu_percent", "%"),
            ("Memory", "memory_percent", "%"),
            ("Disk", "disk_percent", "%"),
            ("Network", "network", ""),
            ("Battery", "battery", ""),
        ]
        self._sys_keys = rows
        for i, (label, key, unit) in enumerate(rows):
            lbl = Gtk.Label(label=label)
            lbl.set_halign(Gtk.Align.START)
            lbl.get_style_context().add_class("subtle")
            val = Gtk.Label(label="—")
            val.set_halign(Gtk.Align.END)
            val.get_style_context().add_class("accent")
            self._sys_grid.attach(lbl, 0, i, 1, 1)
            self._sys_grid.attach(val, 1, i, 1, 1)
            self._sys_vals[key] = (val, unit)

    # ── public API (called by UIBridge) ────────────────────────────────
    def set_orb_state(self, state: str):
        if state in ORB_STATES:
            self.orb.set_state(state)

    def set_orb_caption(self, text: str):
        self._orb_caption.set_text(text)

    def set_status(self, text: str):
        self._status_lbl.set_text(text)
        self.orb.set_label("")

    def add_chat(self, role: str, text: str):
        """role: 'user' | 'jarvis' | 'system'."""
        row = Gtk.ListBoxRow()
        row.get_style_context().add_class(
            "chat-user" if role == "user" else "chat-jarvis" if role == "jarvis" else "chat-sys"
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        if role != "system":
            who = Gtk.Label(label="You" if role == "user" else "JARVIS")
            who.set_halign(Gtk.Align.START)
            who.get_style_context().add_class("subtle")
            box.pack_start(who, False, False, 0)
        msg = Gtk.Label(label=text)
        msg.set_halign(Gtk.Align.START)
        msg.set_line_wrap(True)
        msg.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        msg.set_max_width_chars(60)
        box.pack_start(msg, False, False, 0)
        row.add(box)
        self._chat_list.add(row)
        self._chat_list.show_all()
        # scroll to bottom
        GLib.idle_add(self._scroll_chat_bottom)

    def _scroll_chat_bottom(self):
        adj = self._chat_list.get_parent().get_vadjustment()
        adj.set_value(adj.get_upper())
        return False

    def update_system(self, metrics: dict):
        for label, key, unit in self._sys_keys:
            val, _u = self._sys_vals[key]
            if key == "cpu_percent":
                v = metrics.get("cpu_percent", metrics.get("cpu"))
                val.set_text(f"{v:.0f}%" if isinstance(v, (int, float)) else "—")
            elif key == "memory_percent":
                v = metrics.get("memory_percent", metrics.get("memory"))
                val.set_text(f"{v:.0f}%" if isinstance(v, (int, float)) else "—")
            elif key == "disk_percent":
                v = metrics.get("disk_percent", metrics.get("disk"))
                val.set_text(f"{v:.0f}%" if isinstance(v, (int, float)) else "—")
            elif key == "network":
                connected = metrics.get("network_connected", True)
                val.set_text("Online" if connected else "Offline")
            elif key == "battery":
                b = metrics.get("battery_percent")
                if b is None:
                    val.set_text("AC")
                else:
                    plug = "⚡" if metrics.get("battery_plugged") else ""
                    val.set_text(f"{b:.0f}%{plug}")

    def set_tools_summary(self, text: str):
        self._tools_lbl.set_text(text)

    def set_memory_summary(self, text: str):
        self._mem_lbl.set_text(text)

    def set_entry_text(self, text: str):
        self._entry.set_text(text)
        self._entry.grab_focus()

    def focus_entry(self):
        self._entry.grab_focus()

    # ── input handlers ─────────────────────────────────────────────────
    def _on_entry_activate(self, entry):
        self._send()

    def _on_send_clicked(self, btn):
        self._send()

    def _send(self):
        text = self._entry.get_text().strip()
        if not text:
            return
        self._entry.set_text("")
        if self._on_send:
            self._on_send(text)

    # ── window lifecycle ───────────────────────────────────────────────
    def _do_hide(self):
        self.hide()
        if self._on_hide:
            self._on_hide()

    def _on_delete(self, widget, event):
        # Hide instead of destroy — keeps JARVIS running in background (orb).
        self.hide()
        if self._on_hide:
            self._on_hide()
        return True  # prevent destroy

    def toggle_visible(self):
        if self.get_visible() and self.get_realized():
            self.hide()
        else:
            self.show_all()
            self.present()
