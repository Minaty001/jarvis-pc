"""
JarvisBrain — Main Orchestrator.
Routes user utterances through intent resolution, tool execution, and LLM reasoning.
"""

import json
import re
import time
from typing import Any, Optional

from config.logger import get_logger
from core.intent_resolver import intent_resolver
from core.planner import task_planner
from core.prompt import JARVIS_SYSTEM_PROMPT
from llm.gateway import llm_gateway
from memory.cag_cache import cag_cache
from memory.conversation import conversation_store
from tools.executor import tool_executor

logger = get_logger("core.brain")


class JarvisBrain:
    """Main brain orchestrating intent resolution, tool execution, and LLM reasoning."""

    async def process_utterance(
        self,
        text: str,
        session_id: str = "default",
        request_id: str = None,
    ) -> dict[str, Any]:
        if request_id is None:
            request_id = f"req-{int(time.time() * 1000)}"

        logger.info("Processing: '%s' (session=%s)", text, session_id)

        # Check CAG cache
        cache_hash = cag_cache.compute_hash(text)
        cached = cag_cache.get(cache_hash)
        if cached:
            logger.info("Cache hit")
            return cached

        # Record user message
        conversation_store.record(session_id, "user", text)

        # Plan
        plan = task_planner.plan(text, request_id, session_id)

        # Check if it's a tool action or chat
        step = plan.steps[0] if plan.steps else None
        if step and step.tool != "chat":
            result = await self._execute_tool(step.tool, step.parameters)
            response_text = result.get("result", result.get("message", "Done."))

            response = {
                "type": "command_result",
                "request_id": request_id,
                "session_id": session_id,
                "status": "success",
                "action": step.tool,
                "parameters": step.parameters,
                "response_text": response_text,
                "result": response_text,
            }
        else:
            # LLM reasoning
            response_text = await self._llm_reason(text, session_id)
            response = {
                "type": "chat_response",
                "request_id": request_id,
                "session_id": session_id,
                "status": "success",
                "action": "chat",
                "response_text": response_text,
                "result": response_text,
            }

        # Record and cache
        conversation_store.record(session_id, "assistant", response["response_text"])
        cag_cache.set(cache_hash, response, ttl=300)

        return response

    async def _execute_tool(self, tool: str, params: dict) -> dict[str, Any]:
        """Execute a tool action."""
        try:
            return await tool_executor.execute(tool, params)
        except Exception as e:
            logger.error("Tool execution failed: %s", e)
            return {"success": False, "error": str(e), "result": f"Failed to execute {tool}"}

    async def _llm_reason(self, text: str, session_id: str) -> str:
        """Get LLM response for conversational input."""
        history = conversation_store.get_history(session_id, limit=8)
        history_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in history[:-1]
        ) if len(history) > 1 else ""

        system = JARVIS_SYSTEM_PROMPT
        if history_text:
            system += f"\n\nRecent conversation:\n{history_text}"

        response = await llm_gateway.generate(
            prompt=text,
            system_prompt=system,
        )
        return response.text or "I'm not sure how to help with that, Sir."


jarvis_brain = JarvisBrain()
