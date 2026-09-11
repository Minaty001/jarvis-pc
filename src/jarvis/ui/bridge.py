"""JARVIS UI Bridge — Connects Asyncio Core Application to GTK Main Loop."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Callable, Optional, Dict, Any

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False
    GLib = None  # type: ignore

import psutil

logger = logging.getLogger(__name__)


class UIBridge:
    """Thread-safe bridge between the async agent loop and the GTK event loop."""

    def __init__(self, app_core=None):
        self.app_core = app_core
        self.agent = getattr(app_core, "agent", None)
        self.tools = getattr(app_core, "tools", None)
        self.memory = getattr(app_core, "memory", None)

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._poll_timer_id = None

        # UI Callback hooks
        self.on_orb_state: Optional[Callable[[str], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_chat: Optional[Callable[[str, str], None]] = None
        self.on_system: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_tools: Optional[Callable[[str], None]] = None
        self.on_memory: Optional[Callable[[str], None]] = None
        self.on_waveform: Optional[Callable[[float], None]] = None

        self._voice_session_active = False
        self._voice_thread: Optional[threading.Thread] = None

    def feed_audio_level(self, level: float) -> None:
        """Marshal audio energy level to the GTK thread for waveform display."""
        if self.on_waveform and GTK_AVAILABLE and GLib:
            try:
                GLib.idle_add(self.on_waveform, level)
            except Exception as exc:
                logger.debug("Failed to dispatch audio level to waveform: %s", exc)

    def toggle_voice_session(self, on_active_change: Optional[Callable[[bool], None]] = None) -> bool:
        """Toggle interactive voice assistant session."""
        if self._voice_session_active:
            self._voice_session_active = False
            if on_active_change and GTK_AVAILABLE and GLib:
                GLib.idle_add(on_active_change, False)
            if self.on_status and GTK_AVAILABLE and GLib:
                GLib.idle_add(self.on_status, "Voice Session Stopped")
            if self.on_orb_state and GTK_AVAILABLE and GLib:
                GLib.idle_add(self.on_orb_state, "idle")
            return False

        self._voice_session_active = True
        if on_active_change and GTK_AVAILABLE and GLib:
            GLib.idle_add(on_active_change, True)
        if self.on_status and GTK_AVAILABLE and GLib:
            GLib.idle_add(self.on_status, "Voice Session Active")
        if self.on_orb_state and GTK_AVAILABLE and GLib:
            GLib.idle_add(self.on_orb_state, "listening")

        self._voice_thread = threading.Thread(
            target=self._run_voice_loop_worker,
            daemon=True,
            name="jarvis-voice-ui-worker",
        )
        self._voice_thread.start()
        return True

    def _run_voice_loop_worker(self) -> None:
        """Worker thread running full-duplex voice recognition with barge-in interruption."""
        try:
            from jarvis.voice.duplex import DuplexVoiceSession
            from jarvis.voice.microphone import Microphone
            from jarvis.voice.stt import transcribe_pcm

            def _safe_orb(state: str):
                if self.on_orb_state and GTK_AVAILABLE and GLib:
                    GLib.idle_add(self.on_orb_state, state)

            def _safe_status(status_text: str):
                if self.on_status and GTK_AVAILABLE and GLib:
                    GLib.idle_add(self.on_status, status_text)

            def _safe_chat(role: str, text: str):
                if self.on_chat and GTK_AVAILABLE and GLib:
                    GLib.idle_add(self.on_chat, role, text)

            mic = Microphone()
            session = DuplexVoiceSession(
                on_orb_state=_safe_orb,
                on_status=_safe_status,
                on_chat=_safe_chat,
                on_level=self.feed_audio_level,
            )
        except Exception as exc:
            logger.error("Failed to initialize duplex voice session: %s", exc, exc_info=True)
            if self.on_status and GTK_AVAILABLE and GLib:
                GLib.idle_add(self.on_status, f"Voice init error: {exc}")
            self._voice_session_active = False
            return

        interrupted_pcm: Optional[Any] = None

        while self._voice_session_active and self._running:
            try:
                if interrupted_pcm is not None and len(interrupted_pcm) > 0:
                    pcm = interrupted_pcm
                    interrupted_pcm = None
                else:
                    _safe_orb("listening")
                    _safe_status("Listening...")
                    pcm = mic.record_until_silence(level_callback=self.feed_audio_level)

                if not self._voice_session_active or len(pcm) == 0:
                    continue

                _safe_orb("thinking")
                _safe_status("Transcribing speech...")

                text = transcribe_pcm(pcm)
                if not text or len(text.strip()) < 2:
                    continue

                _safe_chat("user", text)

                reply = "I heard you, sir."
                if self.agent and self._loop:
                    future = asyncio.run_coroutine_threadsafe(
                        self.agent.respond(text, session_id="voice-ui"), self._loop
                    )
                    reply = future.result(timeout=45.0)

                _safe_chat("assistant", reply)

                # Speak with full-duplex barge-in monitoring
                interrupted_pcm = session.speak_and_listen_duplex(reply)

                if interrupted_pcm is not None and len(interrupted_pcm) > 0:
                    _safe_status("User Interrupted — Processing...")
                else:
                    _safe_orb("listening")
                    _safe_status("Voice Session Active")

            except Exception as exc:
                logger.warning("Duplex voice worker iteration error: %s", exc)
                time.sleep(0.5)
                if not self._voice_session_active:
                    break

    def start(self) -> None:
        """Start the background bridge thread and system monitor timer."""
        self._running = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True, name="jarvis-ui-bridge")
        self._thread.start()

        if GTK_AVAILABLE and GLib:
            self._poll_timer_id = GLib.timeout_add(1500, self._poll_metrics)
            # Initial load of tools & memory
            GLib.idle_add(self._load_subsystems_summary)

    def stop(self) -> None:
        """Stop background tasks."""
        self._running = False
        self._voice_session_active = False
        if self._poll_timer_id and GTK_AVAILABLE and GLib:
            GLib.source_remove(self._poll_timer_id)
            self._poll_timer_id = None
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def _run_event_loop(self) -> None:
        if not self._loop:
            return
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        except Exception as exc:
            logger.error("Error in UI bridge event loop: %s", exc)

    def _poll_metrics(self) -> bool:
        """Periodic 1.5s check for CPU, RAM and Disk metrics."""
        if not self._running:
            return False
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
            metrics = {
                "cpu_percent": cpu,
                "ram_percent": ram,
                "disk_percent": disk,
            }
            if self.on_system:
                self.on_system(metrics)
        except Exception as exc:
            logger.debug("System polling error: %s", exc)
        return True

    def _load_subsystems_summary(self) -> bool:
        """Populate initial tools and memory catalog."""
        try:
            # Tools
            if self.tools:
                defs = self.tools.list_tools() if hasattr(self.tools, "list_tools") else []
                lines = ["REGISTERED TOOLS & CAPABILITIES:\n" + "=" * 32]
                for td in defs:
                    lines.append(f"• {td.name} [{td.risk_level.value.upper()}]\n  {td.description}\n")
                if self.on_tools:
                    self.on_tools("\n".join(lines))

            # Memory
            if self.memory:
                episodes = self.memory.recent(limit=10) if hasattr(self.memory, "recent") else []
                lines = ["RECENT MEMORY EPISODES (SQLite FTS5):\n" + "=" * 32]
                for ep in episodes:
                    lines.append(f"[{ep.get('category', 'general')}] {ep.get('content', '')}")
                if self.on_memory:
                    self.on_memory("\n\n".join(lines) if episodes else "No memory episodes recorded yet.")
        except Exception as exc:
            logger.debug("Error loading initial subsystems: %s", exc)
        return False

    def send_chat(self, text: str) -> None:
        """Schedule processing of user chat text asynchronously."""
        if not self._loop or not self._loop.is_running():
            logger.warning("Event loop not running, cannot process chat.")
            return
        asyncio.run_coroutine_threadsafe(self._async_handle_chat(text), self._loop)

    async def _async_handle_chat(self, text: str) -> None:
        self._notify_ui_orb("thinking")
        self._notify_ui_status("PROCESSING GOAL...")

        reply_text = ""
        try:
            if self.agent and hasattr(self.agent, "run_goal"):
                # Run complete goal planner + verifier
                res = await self.agent.run_goal(text)
                if isinstance(res, dict):
                    reply_text = res.get("reply", "Goal executed successfully.")
                else:
                    reply_text = str(res)
            elif self.agent and hasattr(self.agent, "step"):
                reply_text = await self.agent.step(text)
            else:
                reply_text = f"JARVIS received: '{text}'. Core agent is active in mock mode."
        except Exception as exc:
            logger.error("Error executing goal in UI bridge: %s", exc, exc_info=True)
            reply_text = f"An error occurred while processing: {exc}"
            self._notify_ui_orb("error")
        else:
            self._notify_ui_orb("speaking")

        # Send response bubble
        self._notify_ui_chat("assistant", reply_text)

        # Re-fetch memory after response
        if GTK_AVAILABLE and GLib:
            GLib.idle_add(self._load_subsystems_summary)

        # Reset orb state back to idle after brief pause
        await asyncio.sleep(1.2)
        self._notify_ui_orb("idle")
        self._notify_ui_status("STATE: READY")

    def _notify_ui_orb(self, state: str) -> None:
        if GTK_AVAILABLE and GLib and self.on_orb_state:
            GLib.idle_add(self.on_orb_state, state)

    def _notify_ui_status(self, text: str) -> None:
        if GTK_AVAILABLE and GLib and self.on_status:
            GLib.idle_add(self.on_status, text)

    def _notify_ui_chat(self, role: str, text: str) -> None:
        if GTK_AVAILABLE and GLib and self.on_chat:
            GLib.idle_add(self.on_chat, role, text)
