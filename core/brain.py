"""
JarvisBrain — Compatibility wrapper delegating to CognitiveOrchestrator.
All cognitive, planning, security, and verification workflows now pass through
the unified CognitiveOrchestrator runtime engine.
"""

from typing import Any, Optional
from config.logger import get_logger
from cognitive.orchestrator import cognitive_orchestrator

logger = get_logger("core.brain")


class JarvisBrain:
    """Compatibility wrapper delegating all execution to CognitiveOrchestrator."""

    async def process_utterance(
        self,
        text: str,
        session_id: str = "default",
        request_id: str = None,
    ) -> dict[str, Any]:
        logger.info("JarvisBrain delegating '%s' to CognitiveOrchestrator", text[:60])
        return await cognitive_orchestrator.process_goal(
            goal=text,
            session_id=session_id,
            task_id=request_id,
        )


jarvis_brain = JarvisBrain()
