"""
Memory Manager — Unified API over all 6 memory types.
Provides remember, retrieve, search, update, forget, summarize, promote, decay.
"""

import time
from typing import Any, Optional

from config.logger import get_logger
from memory.working_memory import working_memory
from memory.episodic_memory import episodic_memory
from memory.semantic_memory import semantic_memory
from memory.procedural_memory import procedural_memory
from memory.preference_memory import preference_memory
from memory.failure_memory import failure_memory

logger = get_logger("memory.manager")


class MemoryManager:
    """Unified memory interface across all memory types."""

    def __init__(self):
        self.working = working_memory
        self.episodic = episodic_memory
        self.semantic = semantic_memory
        self.procedural = procedural_memory
        self.preference = preference_memory
        self.failure = failure_memory

    async def remember(
        self,
        content: str,
        memory_type: str = "episodic",
        metadata: Optional[dict] = None,
        **kwargs,
    ) -> str:
        """Store a memory of the specified type."""
        if memory_type == "working":
            key = kwargs.get("key", f"mem-{int(time.time())}")
            self.working.set(key, content)
            return key
        elif memory_type == "episodic":
            return self.episodic.remember(
                content=content,
                outcome=kwargs.get("outcome", "unknown"),
                context=metadata,
                tags=kwargs.get("tags", []),
                importance=kwargs.get("importance", 0.5),
            )
        elif memory_type == "semantic":
            return self.semantic.remember(
                content=content,
                category=kwargs.get("category", "general"),
                source=kwargs.get("source", ""),
                confidence=kwargs.get("confidence", 0.9),
                metadata=metadata,
            )
        elif memory_type == "procedural":
            return self.procedural.remember(
                name=kwargs.get("name", content[:50]),
                steps=kwargs.get("steps", [content]),
                context=kwargs.get("context", ""),
                metadata=metadata,
            )
        elif memory_type == "preference":
            return self.preference.remember(
                key=kwargs.get("key", content[:50]),
                value=kwargs.get("value", content),
                category=kwargs.get("category", "general"),
                approved=kwargs.get("approved", True),
            )
        elif memory_type == "failure":
            return self.failure.remember(
                action=kwargs.get("action", ""),
                error=content,
                cause=kwargs.get("cause", ""),
                fix=kwargs.get("fix", ""),
                context=metadata,
            )
        else:
            logger.warning("Unknown memory type: %s", memory_type)
            return ""

    async def retrieve(
        self,
        query: str = "",
        memory_types: Optional[list[str]] = None,
        limit: int = 10,
        **kwargs,
    ) -> list[dict]:
        """Retrieve memories across types, ranked by relevance."""
        if memory_types is None:
            memory_types = ["working", "episodic", "semantic", "procedural", "preference"]

        all_results = []

        for mem_type in memory_types:
            try:
                if mem_type == "working":
                    results = self.working.search(query)
                    for r in results:
                        r["type"] = "working"
                    all_results.extend(results)
                elif mem_type == "episodic":
                    results = self.episodic.retrieve(query=query, limit=limit)
                    for r in results:
                        r["type"] = "episodic"
                    all_results.extend(results)
                elif mem_type == "semantic":
                    results = self.semantic.retrieve(query=query, limit=limit)
                    for r in results:
                        r["type"] = "semantic"
                    all_results.extend(results)
                elif mem_type == "procedural":
                    results = self.procedural.retrieve(query=query, limit=limit)
                    for r in results:
                        r["type"] = "procedural"
                    all_results.extend(results)
                elif mem_type == "preference":
                    results = self.preference.retrieve(query=query, limit=limit)
                    for r in results:
                        r["type"] = "preference"
                    all_results.extend(results)
            except Exception as e:
                logger.error("Failed to retrieve from %s: %s", mem_type, e)

        # Sort by relevance (simple: prefer semantic > episodic > procedural > working)
        type_priority = {"semantic": 4, "episodic": 3, "procedural": 2, "preference": 2, "working": 1}
        all_results.sort(key=lambda r: type_priority.get(r.get("type", ""), 0), reverse=True)

        return all_results[:limit]

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """Semantic search across all memory types."""
        return await self.retrieve(query=query, limit=limit)

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        return self.preference.get(key, default)

    def record_failure(self, action: str, error: str, fix: str = "") -> str:
        """Record a failure for future learning."""
        return self.failure.remember(action=action, error=error, fix=fix)

    def get_similar_failures(self, action: str, error: str) -> list[dict]:
        """Find similar past failures."""
        return self.failure.retrieve(action=action, error=error)

    def summarize_all(self) -> str:
        """Summarize all memory stores."""
        parts = [
            self.working.summarize(),
            self.episodic.summarize(),
            self.semantic.summarize(),
            self.procedural.summarize(),
            self.preference.summarize(),
            self.failure.summarize(),
        ]
        return "\n\n".join(parts)


memory_manager = MemoryManager()
