from __future__ import annotations

import asyncio
import logging
import signal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jarvis.app.application import Application

logger = logging.getLogger(__name__)


def setup_signal_handlers(
    app: Application,
    loop: asyncio.AbstractEventLoop | None = None,
) -> list[signal.Signals]:
    """Register SIGTERM and SIGINT signal handlers for graceful shutdown."""
    if loop is None:
        loop = asyncio.get_running_loop()

    registered_signals = []

    def _handle_signal(sig: signal.Signals) -> None:
        logger.info("Received signal %s, initiating graceful shutdown...", sig.name)
        loop.create_task(app.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_signal, sig)
            registered_signals.append(sig)
        except (NotImplementedError, RuntimeError):
            # Signal handling might not be supported (e.g. non-main thread or Windows)
            logger.warning("Could not register signal handler for %s", sig)

    return registered_signals
