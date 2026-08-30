"""
Event Bus — Pub/sub system for decoupled perception layer.
Supports async handlers, filtering, deduplication, and throttling.
"""

import asyncio
import time
from collections import defaultdict
from typing import Any, Callable, Coroutine, Optional

from config.logger import get_logger
from perception.event_models import Event, EventType, EventSeverity

logger = get_logger("perception.event_bus")


class EventBus:
    """Central event bus for the cognitive engine."""

    def __init__(self, dedup_window_sec: float = 5.0, max_queue_size: int = 1000):
        self._handlers: dict[EventType, list[Callable]] = defaultdict(list)
        self._global_handlers: list[Callable] = []
        self._queue: asyncio.Queue = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._dedup_window = dedup_window_sec
        self._recent_events: dict[str, float] = {}
        self._max_queue_size = max_queue_size
        self._event_count = 0
        self._dropped_count = 0

    async def start(self) -> None:
        """Start the event processing loop."""
        self._queue = asyncio.Queue(maxsize=self._max_queue_size)
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Event bus started (queue=%d)", self._max_queue_size)

    async def stop(self) -> None:
        """Stop the event processing loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Event bus stopped (processed=%d, dropped=%d)", self._event_count, self._dropped_count)

    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """Subscribe to a specific event type."""
        self._handlers[event_type].append(handler)
        logger.debug("Subscribed to %s: %s", event_type.value, handler.__name__)

    def subscribe_all(self, handler: Callable) -> None:
        """Subscribe to all event types."""
        self._global_handlers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        """Unsubscribe from an event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def publish(self, event: Event) -> bool:
        """Publish an event to the bus. Returns False if dropped."""
        # Deduplication check
        dedup_key = f"{event.type.value}:{event.source}:{hash(str(event.payload))}"
        now = time.time()
        if dedup_key in self._recent_events:
            if now - self._recent_events[dedup_key] < self._dedup_window:
                self._dropped_count += 1
                return False
        self._recent_events[dedup_key] = now

        # Cleanup old dedup entries
        if len(self._recent_events) > 1000:
            cutoff = now - self._dedup_window * 2
            self._recent_events = {k: v for k, v in self._recent_events.items() if v > cutoff}

        try:
            self._queue.put_nowait(event)
            self._event_count += 1
            return True
        except asyncio.QueueFull:
            self._dropped_count += 1
            logger.warning("Event queue full, dropping event: %s", event.type.value)
            return False

    async def _process_loop(self) -> None:
        """Main event processing loop."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Event processing error: %s", e)

    async def _dispatch(self, event: Event) -> None:
        """Dispatch event to all registered handlers."""
        # Type-specific handlers
        for handler in self._handlers.get(event.type, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error("Handler error for %s: %s", handler.__name__, e)

        # Global handlers
        for handler in self._global_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error("Global handler error: %s", e)

        event.processed = True

    @property
    def stats(self) -> dict:
        return {
            "queue_size": self._queue.qsize() if self._queue else 0,
            "total_events": self._event_count,
            "dropped_events": self._dropped_count,
            "handlers": sum(len(h) for h in self._handlers.values()) + len(self._global_handlers),
        }


event_bus = EventBus()
