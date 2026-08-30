"""
Task Agent — Execute complex multi-step tasks autonomously.
Can break down goals, execute steps, and self-correct on failure.
"""

import asyncio
from typing import Any

from config.logger import get_logger
from agents.base import AgentResult, BaseAgent
from core.brain import jarvis_brain

logger = get_logger("agents.task")


class TaskAgent(BaseAgent):
    """Agent for executing complex multi-step tasks."""

    def __init__(self, goal: str, max_steps: int = 10):
        super().__init__(name="task-agent")
        self.goal = goal
        self.max_steps = max_steps
        self.steps_taken = 0

    async def run(self, **kwargs) -> AgentResult:
        logger.info("TaskAgent executing goal: '%s'", self.goal)

        context = self.goal
        for step in range(self.max_steps):
            self.steps_taken = step + 1
            result = await jarvis_brain.process_utterance(
                context,
                session_id=f"task-{self.id}",
            )

            action = result.get("action", "chat")
            response = result.get("response_text", "")

            if action == "chat" and step > 0:
                return AgentResult(
                    success=True,
                    output=response,
                    agent_id=self.id,
                    steps_taken=self.steps_taken,
                )

            context = f"Continue task: {self.goal}. Last result: {response}"
            await asyncio.sleep(0.5)

        return AgentResult(
            success=True,
            output=f"Completed {self.steps_taken} steps for: {self.goal}",
            agent_id=self.id,
            steps_taken=self.steps_taken,
        )
