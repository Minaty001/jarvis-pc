"""Metacognitive Reflection Engine for JARVIS (Step 9 of AGI Plan).

Autonomously critiques completed or failed goal execution trajectories,
distilling actionable lessons and reusable procedural recipes to prevent
repeating errors and accelerate future problem solving.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REFLECTION_SYSTEM_PROMPT = """You are JARVIS's metacognitive reflection layer.
Your role is to critique goal execution trajectories, diagnose root causes of failure or identify the critical drivers of success, and extract a concise, actionable rule for future attempts.

Rules:
1. Always output strict valid JSON only, with no markdown code blocks or extra text.
2. JSON schema:
   {
     "category": "tool_usage" | "parameter_fix" | "environment_quirk" | "workflow_strategy",
     "lesson": "Concise 1-2 sentence actionable instruction for future similar tasks",
     "recipe": ["Step 1...", "Step 2..."] or null
   }
3. If the task failed or was unverified, provide a clear diagnostic lesson on what to do differently.
4. If the task succeeded, extract the clean procedural recipe.
"""


class ReflectionEngine:
    """Evaluates goal outcomes and generates structured lessons."""

    def __init__(self, llm_client=None) -> None:
        self.client = llm_client

    async def reflect_on_outcome(
        self,
        goal: str,
        plan: List[Any],
        transcript: List[str],
        verified: bool,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Critique an execution outcome and extract a structured lesson."""
        if not self.client:
            return self._heuristic_reflection(goal, plan, verified, error)

        trajectory_summary = "\n".join(transcript[-8:]) if transcript else "No execution steps recorded."
        plan_summary = "\n".join(f"- {s}" for s in plan) if plan else "None"

        user_content = (
            f"GOAL: {goal}\n"
            f"PLAN:\n{plan_summary}\n\n"
            f"RECENT EXECUTION LOG:\n{trajectory_summary}\n\n"
            f"VERIFIED SUCCESS: {verified}\n"
            f"ERROR: {error or 'None'}\n"
        )

        messages = [
            {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        try:
            raw_reply = await self.client.chat(messages, max_tokens=300)
            clean_reply = raw_reply.strip()
            if clean_reply.startswith("```json"):
                clean_reply = clean_reply[7:]
            if clean_reply.startswith("```"):
                clean_reply = clean_reply[3:]
            if clean_reply.endswith("```"):
                clean_reply = clean_reply[:-3]
            parsed = json.loads(clean_reply.strip())

            return {
                "category": parsed.get("category", "general"),
                "lesson": parsed.get("lesson", f"Outcome for {goal}"),
                "recipe": parsed.get("recipe"),
                "verified": verified,
            }
        except Exception as exc:
            logger.debug("LLM reflection failed, using heuristic fallback: %s", exc)
            return self._heuristic_reflection(goal, plan, verified, error)

    def _heuristic_reflection(
        self,
        goal: str,
        plan: List[Any],
        verified: bool,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fallback deterministic reflection if LLM is unavailable."""
        if verified:
            return {
                "category": "workflow_strategy",
                "lesson": f"Successful pattern for '{goal}': followed {len(plan)} planned steps to verified completion.",
                "recipe": plan if plan else None,
                "verified": True,
            }
        else:
            err_msg = error if error else "outcome unverified"
            return {
                "category": "tool_usage",
                "lesson": f"Failed pattern for '{goal}' ({err_msg}): check tool arguments and verify preconditions before executing.",
                "recipe": None,
                "verified": False,
            }
