"""
Base Agent — Async agent with self-correction and lifecycle management.
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from config.logger import get_logger

logger = get_logger("agents.base")


class AgentState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class AgentResult:
    success: bool
    output: Any = None
    error: Optional[str] = None
    agent_id: str = ""
    steps_taken: int = 0


class BaseAgent(ABC):
    """Base class for all Jarvis sub-agents."""

    def __init__(self, name: str = "base-agent"):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.state = AgentState.IDLE
        self._task: Optional[asyncio.Task] = None

    @abstractmethod
    async def run(self, **kwargs) -> AgentResult:
        ...

    async def start(self, **kwargs) -> None:
        """Start the agent as a background task."""
        self.state = AgentState.RUNNING
        self._task = asyncio.create_task(self._run_wrapper(**kwargs))
        logger.info("Agent '%s' started (id=%s)", self.name, self.id)

    async def _run_wrapper(self, **kwargs) -> None:
        try:
            result = await self.run(**kwargs)
            if result.success:
                logger.info("Agent '%s' completed: %s", self.name, result.output)
            else:
                logger.warning("Agent '%s' failed: %s", self.name, result.error)
        except Exception as e:
            logger.error("Agent '%s' crashed: %s", self.name, e)
        finally:
            self.state = AgentState.IDLE

    async def stop(self) -> None:
        """Stop the agent."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.state = AgentState.STOPPED
        logger.info("Agent '%s' stopped", self.name)

    @property
    def is_running(self) -> bool:
        return self.state == AgentState.RUNNING
