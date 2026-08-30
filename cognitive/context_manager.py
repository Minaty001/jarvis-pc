"""
Context Manager — Structured context assembly for LLM calls.
Manages token budgets, progressive retrieval, and context window limits.
"""

from typing import Any, Optional

from config.logger import get_logger
from cognitive.world_state import WorldState

logger = get_logger("cognitive.context")


class ContextManager:
    """Assembles structured context for LLM prompts without overwhelming context window."""

    # Approximate chars per token
    CHARS_PER_TOKEN = 4

    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
        self.max_chars = max_tokens * self.CHARS_PER_TOKEN

    def build_context(
        self,
        user_message: str,
        world_state: Optional[WorldState] = None,
        memories: Optional[list[dict]] = None,
        conversation_history: Optional[list[dict]] = None,
        extra: Optional[dict] = None,
    ) -> str:
        """Build structured context string within token budget."""
        sections = []

        # Priority 1: World state (compact)
        if world_state:
            state_str = world_state.to_context_string()
            sections.append(f"[SYSTEM STATE]\n{state_str}")

        # Priority 2: Recent conversation (last 6 messages)
        if conversation_history:
            recent = conversation_history[-6:]
            conv_lines = []
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:200]
                conv_lines.append(f"{role}: {content}")
            sections.append(f"[RECENT CONVERSATION]\n" + "\n".join(conv_lines))

        # Priority 3: Relevant memories (top 5)
        if memories:
            mem_lines = []
            for mem in memories[:5]:
                mem_lines.append(f"- [{mem.get('type', '?')}] {mem.get('content', '')[:150]}")
            sections.append(f"[RELEVANT MEMORY]\n" + "\n".join(mem_lines))

        # Priority 4: Extra context
        if extra:
            extra_lines = [f"- {k}: {v}" for k, v in list(extra.items())[:5]]
            sections.append(f"[CONTEXT]\n" + "\n".join(extra_lines))

        # Assemble and truncate to budget
        full_context = "\n\n".join(sections)
        if len(full_context) > self.max_chars:
            full_context = full_context[:self.max_chars] + "\n[... truncated ...]"

        return full_context

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return len(text) // self.CHARS_PER_TOKEN

    def truncate_to_budget(self, text: str, budget_tokens: int) -> str:
        """Truncate text to fit within token budget."""
        max_chars = budget_tokens * self.CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n[... truncated ...]"


context_manager = ContextManager()
