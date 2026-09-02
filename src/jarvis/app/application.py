from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Application:
    """Central Application lifecycle manager for JARVIS-PC."""

    def __init__(
        self,
        *,
        voice: Any = None,
        scheduler: Any = None,
        api: Any = None,
    ) -> None:
        self.voice = voice
        self.scheduler = scheduler
        self.api = api

        self._started: bool = False
        self._stopping: bool = False

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
        logger.info("JARVIS started successfully")

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
