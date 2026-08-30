"""
Agent Orchestrator — Coordinate multiple sub-agents.
Manages agent lifecycle, delegation, and status.
"""

import asyncio
from typing import Any, Optional

from config.logger import get_logger
from agents.base import BaseAgent, AgentState

logger = get_logger("agents.orchestrator")


class AgentOrchestrator:
    """Manages all active sub-agents."""

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.id] = agent
        logger.info("Registered agent: %s (id=%s)", agent.name, agent.id)

    def unregister(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)

    async def start_agent(self, agent: BaseAgent, **kwargs) -> None:
        self.register(agent)
        await agent.start(**kwargs)

    async def stop_agent(self, agent_id: str) -> None:
        agent = self._agents.get(agent_id)
        if agent:
            await agent.stop()
            self.unregister(agent_id)

    async def stop_all(self) -> None:
        for agent_id in list(self._agents.keys()):
            await self.stop_agent(agent_id)

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {"id": a.id, "name": a.name, "state": a.state.value}
            for a in self._agents.values()
        ]

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        return self._agents.get(agent_id)


agent_orchestrator = AgentOrchestrator()
