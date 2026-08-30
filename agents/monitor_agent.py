"""
Monitor Agent — Watch files/folders for changes and trigger actions.
"""

import asyncio
from pathlib import Path
from typing import Any, Callable, Optional

from config.logger import get_logger
from agents.base import AgentResult, BaseAgent

logger = get_logger("agents.monitor")

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


class _ChangeHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback

    def on_any_event(self, event):
        if not event.is_directory:
            self.callback(event)


class MonitorAgent(BaseAgent):
    """Agent that watches file system changes and triggers callbacks."""

    def __init__(self, path: str, callback: Optional[Callable] = None, patterns: list[str] = None):
        super().__init__(name="monitor-agent")
        self.watch_path = Path(path)
        self.callback = callback
        self.patterns = patterns or ["*"]
        self._observer = None

    async def run(self, **kwargs) -> AgentResult:
        if not HAS_WATCHDOG:
            return AgentResult(success=False, error="watchdog not installed")

        if not self.watch_path.exists():
            return AgentResult(success=False, error=f"Path not found: {self.watch_path}")

        handler = _ChangeHandler(self._handle_change)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.watch_path), recursive=True)
        self._observer.start()

        logger.info("Monitoring: %s", self.watch_path)

        try:
            while self.is_running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            if self._observer:
                self._observer.stop()
                self._observer.join()

        return AgentResult(success=True, output=f"Stopped monitoring {self.watch_path}")

    def _handle_change(self, event) -> None:
        logger.info("Change detected: %s", event.src_path)
        if self.callback:
            try:
                self.callback(event)
            except Exception as e:
                logger.error("Monitor callback error: %s", e)
