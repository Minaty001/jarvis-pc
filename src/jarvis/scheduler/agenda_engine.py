"""Agenda, Countdown Timers, and Reminders Engine for JARVIS PC."""

from __future__ import annotations

import asyncio
import datetime
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from jarvis.scheduler.agenda_store import AgendaItem, AgendaStore
from jarvis.scheduler.time_parser import parse_time_expression
from jarvis.system.notifications import notify
from jarvis.voice.tts import speak_interruptible

logger = logging.getLogger(__name__)


class AgendaEngine:
    """Manages active timers, scheduled reminders, and due-time alert dispatching."""

    def __init__(
        self,
        store: Optional[AgendaStore] = None,
        on_alert: Optional[Callable[[AgendaItem], None]] = None,
        poll_interval: float = 2.0,
    ) -> None:
        self.store = store or AgendaStore()
        self.on_alert = on_alert
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        return self._running

    def set_timer(self, duration_expr: str, label: str = "Timer") -> Tuple[int, datetime.datetime, float]:
        """Set a countdown timer from duration expression (e.g. '10m', '45s', '1h 30m')."""
        target_dt, sec = parse_time_expression(duration_expr)
        item_id = self.store.add_item(
            title=label.strip() or "Timer",
            due_timestamp=target_dt.timestamp(),
            item_type="timer",
            speak_prompt=f"Timer alert: {label}",
        )
        return item_id, target_dt, sec

    def add_reminder(
        self,
        when_expr: str,
        title: str,
        recurring: Optional[str] = None,
    ) -> Tuple[int, datetime.datetime, float]:
        """Add a scheduled reminder (e.g. 'tomorrow at 3pm', 'in 2 hours')."""
        target_dt, sec = parse_time_expression(when_expr)
        item_id = self.store.add_item(
            title=title.strip(),
            due_timestamp=target_dt.timestamp(),
            item_type="reminder",
            recurring=recurring,
            speak_prompt=f"Scheduled reminder: {title}",
        )
        return item_id, target_dt, sec

    def list_agenda(self, status: Optional[str] = "pending") -> List[AgendaItem]:
        """List active or all agenda items."""
        return self.store.list_items(status=status)

    def cancel_item(self, item_id: int) -> bool:
        """Cancel an agenda item or timer."""
        return self.store.update_status(item_id, "cancelled")

    def dispatch_alert(self, item: AgendaItem) -> None:
        """Deliver desktop notification and vocalized announcement for a due item."""
        type_str = item.item_type.upper()
        title = f"JARVIS {type_str}"
        msg = item.title

        # 1. Desktop notification
        try:
            notify(title, msg, urgency="critical" if item.item_type == "timer" else "normal")
        except Exception as exc:
            logger.debug("Notification dispatch error: %s", exc)

        # 2. Vocal alert
        try:
            prompt = item.speak_prompt or f"Attention, sir. Your {item.item_type} for '{item.title}' is due."
            asyncio.create_task(speak_interruptible(prompt))
        except Exception as exc:
            logger.debug("TTS voice alert dispatch error: %s", exc)

        # 3. Custom callback if hooked
        if self.on_alert:
            try:
                self.on_alert(item)
            except Exception as exc:
                logger.warning("on_alert callback error: %s", exc)

    def process_due_items(self) -> List[AgendaItem]:
        """Check and process all currently due agenda items."""
        due_items = self.store.get_due_items()
        for item in due_items:
            logger.info("Triggering due %s (#%d): '%s'", item.item_type, item.id, item.title)
            self.dispatch_alert(item)

            if item.recurring:
                self.store.reschedule_recurring(item.id)
            else:
                self.store.update_status(item.id, "completed")

        return due_items

    async def _async_loop(self) -> None:
        """Asyncio background polling loop."""
        while self._running:
            try:
                self.process_due_items()
            except Exception as exc:
                logger.error("Error checking due agenda items: %s", exc)
            await asyncio.sleep(self.poll_interval)

    def start(self) -> None:
        """Start the agenda engine daemon in background."""
        if self._running:
            return
        self._running = True

        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._async_loop())
        except RuntimeError:
            # Run in dedicated worker thread
            def _thread_target():
                asyncio.run(self._async_loop())

            self._thread = threading.Thread(target=_thread_target, daemon=True)
            self._thread.start()

        logger.info("AgendaEngine background poller started.")

    def stop(self) -> None:
        """Stop the background agenda engine."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("AgendaEngine background poller stopped.")


_ENGINE_INSTANCE: Optional[AgendaEngine] = None


def get_agenda_engine() -> AgendaEngine:
    """Get or create singleton AgendaEngine."""
    global _ENGINE_INSTANCE
    if _ENGINE_INSTANCE is None:
        _ENGINE_INSTANCE = AgendaEngine()
    return _ENGINE_INSTANCE
