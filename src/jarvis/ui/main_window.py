"""JARVIS Main HUD & Dashboard Window — Chat, System Monitor, Tools & Memory."""

from __future__ import annotations

import logging
from typing import Callable, Dict, Any, Optional

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, GLib
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False
    Gtk = object  # type: ignore

from jarvis.ui.orb import OrbWidget
from jarvis.ui.waveform import WaveformWidget

logger = logging.getLogger(__name__)


class MainWindow(Gtk.Window if GTK_AVAILABLE else object):  # type: ignore
    """Main desktop HUD window containing the Arc-Reactor, Chat, and Subsystems."""

    def __init__(
        self,
        app=None,
        on_send: Optional[Callable[[str], None]] = None,
        on_hide: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
    ):
        if not GTK_AVAILABLE:
            raise RuntimeError("GTK 3.0 is not available.")
        super().__init__()
        self.app = app
        self.on_send = on_send
        self.on_hide_cb = on_hide
        self.on_quit_cb = on_quit

        self.set_title("JARVIS PC — Personal AI Voice Assistant")
        self.set_default_size(960, 640)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.get_style_context().add_class("background")

        self.connect("delete-event", self._on_delete_event)

        # Main horizontal layout
        root_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        root_box.set_margin_top(16)
        root_box.set_margin_bottom(16)
        root_box.set_margin_start(16)
        root_box.set_margin_end(16)
        self.add(root_box)

        # ── Left Column: HUD & Orb Panel ─────────────────────────────────
        left_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        left_panel.get_style_context().add_class("jarvis-surface")
        left_panel.set_size_request(280, -1)
        left_panel.set_margin_top(4)
        left_panel.set_margin_bottom(4)
        left_panel.set_margin_start(4)
        left_panel.set_margin_end(4)

        # Title
        lbl_title = Gtk.Label(label="JARVIS CORE")
        lbl_title.get_style_context().add_class("title")
        lbl_title.set_margin_top(16)
        left_panel.pack_start(lbl_title, False, False, 0)

        # Orb centerpiece
        orb_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        orb_container.get_style_context().add_class("orb-frame")
        self.orb = OrbWidget(size=220, state="idle")
        orb_container.pack_start(self.orb, True, True, 8)
        left_panel.pack_start(orb_container, False, False, 0)

        # Real-time Voice Waveform Visualizer
        self.waveform = WaveformWidget(width=240, height=44, state="idle")
        left_panel.pack_start(self.waveform, False, False, 0)

        # Status text
        self.lbl_status = Gtk.Label(label="STATE: READY")
        self.lbl_status.get_style_context().add_class("accent")
        left_panel.pack_start(self.lbl_status, False, False, 0)

        # Voice Session Toggle Button
        self.btn_voice = Gtk.Button(label="🎙️ Start Voice Session")
        self.btn_voice.connect("clicked", self._on_toggle_voice)
        left_panel.pack_start(self.btn_voice, False, False, 4)

        # Quick Actions
        lbl_actions = Gtk.Label(label="QUICK GOALS")
        lbl_actions.get_style_context().add_class("subtle")
        lbl_actions.set_margin_top(12)
        left_panel.pack_start(lbl_actions, False, False, 0)

        btn_health = Gtk.Button(label="System Health Check")
        btn_health.connect("clicked", lambda _: self._send_quick_prompt("Check system health and status"))
        left_panel.pack_start(btn_health, False, False, 0)

        btn_procs = Gtk.Button(label="Top Active Processes")
        btn_procs.connect("clicked", lambda _: self._send_quick_prompt("List top 5 processes by CPU and memory"))
        left_panel.pack_start(btn_procs, False, False, 0)

        btn_hide = Gtk.Button(label="Minimize to Floating Orb")
        btn_hide.connect("clicked", lambda _: self.hide())
        left_panel.pack_end(btn_hide, False, False, 12)

        root_box.pack_start(left_panel, False, False, 0)

        # ── Right Column: Notebook Tabs ──────────────────────────────────
        notebook = Gtk.Notebook()
        notebook.get_style_context().add_class("jarvis-surface")
        root_box.pack_start(notebook, True, True, 0)

        # Tab 1: Interactive Chat
        chat_box = self._build_chat_tab()
        notebook.append_page(chat_box, Gtk.Label(label="Chat & Tasks"))

        # Tab 2: System Monitor
        sys_box = self._build_system_tab()
        notebook.append_page(sys_box, Gtk.Label(label="System Monitor"))

        # Tab 3: Tools Catalog
        tools_box = self._build_tools_tab()
        notebook.append_page(tools_box, Gtk.Label(label="Registered Tools"))

        # Tab 4: Memory Explorer
        mem_box = self._build_memory_tab()
        notebook.append_page(mem_box, Gtk.Label(label="Memory & Context"))

    # ── Builders ────────────────────────────────────────────────────────
    def _build_chat_tab(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)
        vbox.set_margin_start(8)
        vbox.set_margin_end(8)

        # Scrollable chat history
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.get_style_context().add_class("chat-scroll")
        self.chat_history_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.chat_history_box.set_margin_top(8)
        self.chat_history_box.set_margin_bottom(8)
        self.chat_history_box.set_margin_start(8)
        self.chat_history_box.set_margin_end(8)
        scroll.add(self.chat_history_box)
        vbox.pack_start(scroll, True, True, 0)
        self.chat_scroll = scroll

        # Chat Input Box
        input_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.chat_entry = Gtk.Entry()
        self.chat_entry.set_placeholder_text("Ask JARVIS or give a goal (e.g. 'Check CPU usage', 'Open Firefox')...")
        self.chat_entry.connect("activate", self._on_chat_submit)
        input_bar.pack_start(self.chat_entry, True, True, 0)

        btn_send = Gtk.Button(label="Send")
        btn_send.get_style_context().add_class("suggested-action")
        btn_send.connect("clicked", self._on_chat_submit)
        input_bar.pack_start(btn_send, False, False, 0)

        vbox.pack_start(input_bar, False, False, 0)
        return vbox

    def _build_system_tab(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)

        # CPU
        self.lbl_cpu = Gtk.Label(label="CPU Usage: 0%")
        self.lbl_cpu.set_xalign(0.0)
        vbox.pack_start(self.lbl_cpu, False, False, 0)
        self.prog_cpu = Gtk.ProgressBar()
        vbox.pack_start(self.prog_cpu, False, False, 0)

        # RAM
        self.lbl_ram = Gtk.Label(label="Memory Usage: 0%")
        self.lbl_ram.set_xalign(0.0)
        vbox.pack_start(self.lbl_ram, False, False, 0)
        self.prog_ram = Gtk.ProgressBar()
        vbox.pack_start(self.prog_ram, False, False, 0)

        # Disk
        self.lbl_disk = Gtk.Label(label="Disk Usage: 0%")
        self.lbl_disk.set_xalign(0.0)
        vbox.pack_start(self.lbl_disk, False, False, 0)
        self.prog_disk = Gtk.ProgressBar()
        vbox.pack_start(self.prog_disk, False, False, 0)

        return vbox

    def _build_tools_tab(self) -> Gtk.Widget:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.txt_tools = Gtk.TextView()
        self.txt_tools.set_editable(False)
        self.txt_tools.set_cursor_visible(False)
        self.txt_tools.set_left_margin(12)
        self.txt_tools.set_right_margin(12)
        scroll.add(self.txt_tools)
        return scroll

    def _build_memory_tab(self) -> Gtk.Widget:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.txt_memory = Gtk.TextView()
        self.txt_memory.set_editable(False)
        self.txt_memory.set_cursor_visible(False)
        self.txt_memory.set_left_margin(12)
        self.txt_memory.set_right_margin(12)
        scroll.add(self.txt_memory)
        return scroll

    # ── Public UI Updates ──────────────────────────────────────────────
    def set_status(self, text: str) -> None:
        self.lbl_status.set_text(text)

    def set_orb_state(self, state: str) -> None:
        if self.orb:
            self.orb.set_state(state)
        if hasattr(self, "waveform") and self.waveform:
            self.waveform.set_state(state)

    def update_waveform(self, level: float) -> None:
        if hasattr(self, "waveform") and self.waveform:
            self.waveform.feed_level(level)

    def _on_toggle_voice(self, _button) -> None:
        bridge = getattr(self.app, "bridge", None)
        if bridge and hasattr(bridge, "toggle_voice_session"):
            bridge.toggle_voice_session(on_active_change=self.set_voice_active)

    def set_voice_active(self, active: bool) -> None:
        if hasattr(self, "btn_voice"):
            if active:
                self.btn_voice.set_label("⏹️ Stop Voice Session")
                self.btn_voice.get_style_context().add_class("destructive")
            else:
                self.btn_voice.set_label("🎙️ Start Voice Session")
                self.btn_voice.get_style_context().remove_class("destructive")

    def add_chat(self, role: str, text: str) -> None:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        lbl = Gtk.Label(label=text)
        lbl.set_line_wrap(True)
        lbl.set_max_width_chars(54)
        lbl.set_selectable(True)

        if role == "user":
            lbl.get_style_context().add_class("chat-user")
            row.pack_end(lbl, False, False, 4)
        elif role == "assistant":
            lbl.get_style_context().add_class("chat-jarvis")
            row.pack_start(lbl, False, False, 4)
        else:
            lbl.get_style_context().add_class("chat-sys")
            row.pack_start(lbl, True, True, 4)

        row.show_all()
        self.chat_history_box.pack_start(row, False, False, 0)

        # Scroll down
        GLib.idle_add(self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> bool:
        adj = self.chat_scroll.get_vadjustment()
        if adj:
            adj.set_value(adj.get_upper() - adj.get_page_size())
        return False

    def update_system(self, metrics: Dict[str, Any]) -> None:
        cpu = metrics.get("cpu_percent", 0.0)
        self.prog_cpu.set_fraction(max(0.0, min(1.0, cpu / 100.0)))
        self.lbl_cpu.set_text(f"CPU Usage: {cpu:.1f}%")

        ram = metrics.get("ram_percent", 0.0)
        self.prog_ram.set_fraction(max(0.0, min(1.0, ram / 100.0)))
        self.lbl_ram.set_text(f"Memory Usage: {ram:.1f}%")

        disk = metrics.get("disk_percent", 0.0)
        self.prog_disk.set_fraction(max(0.0, min(1.0, disk / 100.0)))
        self.lbl_disk.set_text(f"Disk Usage: {disk:.1f}%")

    def set_tools_summary(self, text: str) -> None:
        buf = self.txt_tools.get_buffer()
        buf.set_text(text)

    def set_memory_summary(self, text: str) -> None:
        buf = self.txt_memory.get_buffer()
        buf.set_text(text)

    # ── Events ──────────────────────────────────────────────────────────
    def _on_chat_submit(self, _widget) -> None:
        text = self.chat_entry.get_text().strip()
        if not text:
            return
        self.chat_entry.set_text("")
        self.add_chat("user", text)
        if self.on_send:
            self.on_send(text)

    def _send_quick_prompt(self, prompt: str) -> None:
        self.add_chat("user", prompt)
        if self.on_send:
            self.on_send(prompt)

    def _on_delete_event(self, _widget, _event) -> bool:
        # Hide instead of terminating app
        self.hide()
        if self.on_hide_cb:
            self.on_hide_cb()
        return True
