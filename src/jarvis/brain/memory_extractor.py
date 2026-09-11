"""Autonomous memory extraction pipeline for JARVIS.

Extracts user preferences, identity attributes, project context, and long-term facts
from conversational turns and commits them to SQLite semantic memory.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def _clean_val(val: str) -> str:
    """Strip trailing conjunctions and punctuation."""
    v = re.split(r"\b(?:and|but|while|also|with)\b|[,;.!?\n]", val, flags=re.IGNORECASE)[0]
    return v.strip()


# Heuristic extraction patterns: (regex_pattern, default_key, category)
_PATTERNS = [
    (
        re.compile(r"(?:my name is|call me)\s+([A-Za-z0-9_\-\s]{2,40})", re.IGNORECASE),
        "name",
        "personal",
    ),
    (
        re.compile(r"(?:my (?:fav|favorite|favourite)\s+([a-zA-Z\s]+)\s+is\s+([^.,!\n]+))", re.IGNORECASE),
        None,  # dynamic key: favorite_<item>
        "preference",
    ),
    (
        re.compile(r"(?:i prefer\s+([^.,!\n]+))", re.IGNORECASE),
        "preference",
        "preference",
    ),
    (
        re.compile(r"(?:remember that|remember:?)\s+([^.,!\n]+)", re.IGNORECASE),
        "explicit_fact",
        "user_fact",
    ),
    (
        re.compile(r"(?:i (?:live in|am based in|am located in)|my city is|my location is)\s+([^.,!\n]+)", re.IGNORECASE),
        "location",
        "personal",
    ),
    (
        re.compile(r"(?:i (?:use|code with|work with)|my (?:preferred|default)?\s*(?:editor|ide)\s+is)\s+([^.,!\n]+)", re.IGNORECASE),
        "editor",
        "tools",
    ),
    (
        re.compile(r"(?:i am working on|my project is|my current project is)\s+([^.,!\n]+)", re.IGNORECASE),
        "current_project",
        "work",
    ),
    (
        re.compile(r"(?:my timezone is|timezone is)\s+([^.,!\n]+)", re.IGNORECASE),
        "timezone",
        "personal",
    ),
]


class MemoryExtractor:
    """Extracts facts, preferences, and user profile properties from conversations."""

    def __init__(self, llm_client: Any = None) -> None:
        self.llm_client = llm_client

    def extract_heuristics(self, text: str) -> List[Dict[str, Any]]:
        """Fast regex/pattern extraction for common user statements."""
        extracted: List[Dict[str, Any]] = []
        clean = text.strip()

        for pattern, default_key, category in _PATTERNS:
            match = pattern.search(clean)
            if not match:
                continue

            groups = match.groups()
            if len(groups) == 1:
                val = _clean_val(groups[0])
                key = default_key or "fact"
                if val:
                    extracted.append({
                        "key": key,
                        "value": val,
                        "category": category,
                        "confidence": 0.95,
                    })
            elif len(groups) >= 2:
                # E.g. favorite <item> is <val>
                item = groups[0].strip().lower().replace(" ", "_")
                val = _clean_val(groups[1])
                key = f"favorite_{item}" if default_key is None else default_key
                if val:
                    extracted.append({
                        "key": key,
                        "value": val,
                        "category": category,
                        "confidence": 0.95,
                    })

        return extracted

    async def extract_llm(self, user_text: str, assistant_reply: str) -> List[Dict[str, Any]]:
        """LLM-driven semantic fact extraction for complex conversational context."""
        if not self.llm_client:
            return []

        prompt = (
            "Analyze this user message and extract any explicit user preferences, personal details, "
            "developer tools, project names, or long-term facts mentioned by the user.\n"
            f"User message: \"{user_text}\"\n"
            "Output JSON ONLY as a list of objects with fields 'key' (string, snake_case), 'value' (string), and 'category' ('preference'|'personal'|'work'|'tools'|'general').\n"
            "If no meaningful persistent facts or preferences are found, output: []"
        )

        try:
            res = await self.llm_client.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            content = res.content.strip() if res and res.content else "[]"
            # Extract json array substring
            match = re.search(r"\[.*\]", content, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    return [
                        {
                            "key": item.get("key", "fact").strip().lower().replace(" ", "_"),
                            "value": str(item.get("value", "")).strip(),
                            "category": str(item.get("category", "general")).strip().lower(),
                            "confidence": 0.85,
                        }
                        for item in parsed
                        if item.get("key") and item.get("value")
                    ]
        except Exception as exc:
            logger.debug("LLM memory extraction skipped or error: %s", exc)

        return []

    async def extract_and_store(
        self,
        user_text: str,
        assistant_reply: str,
        memory: Any,
        use_llm: bool = False,
    ) -> List[Dict[str, Any]]:
        """Extract facts and persist them into MemoryStore."""
        if not memory:
            return []

        # 1. Rule-based fast extraction
        facts = self.extract_heuristics(user_text)

        # 2. LLM fallback if enabled and no heuristics matched
        if not facts and use_llm and self.llm_client:
            facts = await self.extract_llm(user_text, assistant_reply)

        stored_facts = []
        for f in facts:
            fact_id = memory.store_fact(
                key=f["key"],
                value=f["value"],
                category=f.get("category", "general"),
                subject="user",
                predicate="preference",
                confidence=f.get("confidence", 1.0),
                source="auto_extract",
            )
            stored_facts.append({**f, "id": fact_id})

        return stored_facts
