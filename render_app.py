"""
Render.com Production Deployment Entry Point — JARVIS Headless Backend API.
Boots cognitive engine, tools, memory, and HTTP REST API server for cloud execution.
"""

import asyncio
import os
import signal
import sys
from pathlib import Path

# Insert project root in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.logger import get_logger, setup_logging
from run import _bootstrap_engine, _shutdown_engine

logger = get_logger("render.main")
_running = True


def _signal_handler(sig, frame):
    global _running
    logger.info("Signal %s received, shutting down Render backend...", sig)
    _running = False


async def main():
    setup_logging("INFO")
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "10000"))

    logger.info("=" * 60)
    logger.info("  JARVIS PC — Render.com Production API Server")
    logger.info("  Host: %s | Port: %d", host, port)
    logger.info("=" * 60)

    # Bootstrap cognitive engine, memory, tools, and API server
    bundle = await _bootstrap_engine()

    logger.info("Render.com Backend is live and listening on http://%s:%d", host, port)
    logger.info("Health check endpoint: http://%s:%d/health", host, port)

    try:
        while _running:
            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        pass
    finally:
        await _shutdown_engine(bundle)


if __name__ == "__main__":
    asyncio.run(main())
