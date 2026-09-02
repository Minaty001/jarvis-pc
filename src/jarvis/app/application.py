from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

logger = logging.getLogger(__name__)


class Application:
    """Central Application lifecycle manager and composition root for JARVIS-PC."""

    def __init__(self, *, settings=None) -> None:
        from jarvis.tools.registry import ToolRegistry
        from jarvis.tools.executor import ToolExecutor
        from jarvis.tools.builtin.registry_init import register_all_builtins

        if settings is None:
            from jarvis.config.settings import get_settings
            settings = get_settings()

        self.settings = settings
        self.registry = ToolRegistry()
        register_all_builtins(self.registry)
        self.executor = ToolExecutor(registry=self.registry)

        self.voice: Any = None
        self.scheduler: Any = None
        self.api: Any = None

        self._started: bool = False
        self._stopping: bool = False
        self._stop_event: asyncio.Event | None = None

    @property
    def is_started(self) -> bool:
        return self._started

    async def start(self) -> None:
        if self._started:
            return

        logger.info("Starting JARVIS application")
        components = [self.scheduler, self.voice, self.api]
        started_components: list[Any] = []

        try:
            for component in components:
                if component is not None and hasattr(component, "start") and callable(component.start):
                    await component.start()
                    started_components.append(component)
        except Exception:
            logger.exception("Application startup failed; rolling back started components")
            for component in reversed(started_components):
                if hasattr(component, "stop") and callable(component.stop):
                    try:
                        await component.stop()
                    except Exception as stop_exc:
                        logger.exception("Failed stopping component during rollback: %r", stop_exc)
            raise

        self._started = True
        logger.info("JARVIS started successfully (%d tools registered)", len(self.registry.list()))

    async def stop(self) -> None:
        if not self._started or self._stopping:
            return

        self._stopping = True
        logger.info("Stopping JARVIS application")
        errors: list[Exception] = []

        for component in (self.api, self.voice, self.scheduler):
            if component is None:
                continue
            if hasattr(component, "stop") and callable(component.stop):
                try:
                    await component.stop()
                except Exception as exc:
                    logger.exception("Failed stopping %r", component)
                    errors.append(exc)

        self._started = False
        self._stopping = False

        if errors:
            raise RuntimeError(f"{len(errors)} component(s) failed to stop")

    async def run_until_stopped(self) -> None:
        """Start application and block until stop signal received."""
        await self.start()
        self._stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._stop_event.set)
        logger.info("JARVIS running. Press Ctrl+C to stop.")
        await self._stop_event.wait()
        await self.stop()

    def request_stop(self) -> None:
        """Programmatically request graceful shutdown."""
        if self._stop_event:
            self._stop_event.set()
