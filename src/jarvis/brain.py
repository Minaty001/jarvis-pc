"""Conversational Intelligence and LLM Brain Fallback for JARVIS.

Provides fast, natural voice responses to general knowledge, conversational,
and reasoning queries using OpenAI-compatible endpoints (Groq, OpenRouter,
Ollama, Gemini, OpenAI) with a graceful offline rule-based fallback.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

import httpx

from .config import LLMConfig, get_llm_config

logger = logging.getLogger("jarvis.brain")

SYSTEM_PROMPT = (
    "You are JARVIS, an intelligent, concise personal voice AI assistant. "
    "Answer directly in 1 to 2 spoken sentences (under 35 words). "
    "Do NOT use markdown, asterisks, bullet points, numbered lists, or code blocks. "
    "Speak naturally to the user whom you address as 'boss'."
)


class LLMBrain:
    """Conversational LLM engine for voice queries."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or get_llm_config()

    def ask(self, query: str) -> str:
        """Process an arbitrary natural language query and return concise spoken answer."""
        clean_query = query.strip()
        if not clean_query:
            return "I am here, boss. How can I help you?"

        # 1. Quick local math evaluation
        math_answer = self._solve_simple_math(clean_query)
        if math_answer is not None:
            return math_answer

        # 2. Try LLM API call
        llm_response = self._call_llm(clean_query)
        if llm_response:
            return self._clean_speech_output(llm_response)

        # 3. Graceful offline fallback
        return self._offline_fallback(clean_query)

    def _call_llm(self, query: str) -> Optional[str]:
        """Send chat completion request to configured OpenAI-compatible endpoint."""
        # If provider is not Ollama and no real API key is set, skip API call
        if self.config.provider != "ollama" and (not self.config.api_key or "your_" in self.config.api_key):
            logger.debug("No active LLM API key configured for provider '%s'.", self.config.provider)
            return None

        endpoint = f"{self.config.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            "max_tokens": 100,
            "temperature": 0.6,
        }

        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                resp = client.post(endpoint, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        if content:
                            return content.strip()
                else:
                    logger.warning("LLM API returned HTTP %s: %s", resp.status_code, resp.text[:150])
        except Exception as err:
            logger.debug("LLM query to '%s' failed: %s", endpoint, err)

        return None

    def _clean_speech_output(self, text: str) -> str:
        """Strip markdown syntax and formatting for clean voice synthesis."""
        clean = text.strip()

        # Remove markdown bold/italic/headers/code
        clean = re.sub(r"[*_#`~>]", "", clean)
        clean = re.sub(r"\[.*?\]\(.*?\)", "", clean)  # remove links
        clean = re.sub(r"\s+", " ", clean).strip()

        # Strip prefixes like "JARVIS:" or "Assistant:"
        clean = re.sub(r"^(?:JARVIS|Assistant):\s*", "", clean, flags=re.IGNORECASE)

        # Strip surrounding quotation marks
        if clean.startswith('"') and clean.endswith('"'):
            clean = clean[1:-1].strip()

        return clean

    def _solve_simple_math(self, query: str) -> Optional[str]:
        """Evaluate simple arithmetic queries locally without API calls."""
        # e.g., "what is 25 times 4", "what is 10 plus 15", "calculate 100 / 5"
        normalized = query.lower()
        normalized = re.sub(r"^(?:what\s+is|calculate|evaluate|how\s+much\s+is)\s+", "", normalized)
        normalized = normalized.rstrip("?").strip()

        # Replace verbal operators
        normalized = re.sub(r"\bplus\b", "+", normalized)
        normalized = re.sub(r"\bminus\b", "-", normalized)
        normalized = re.sub(r"\btimes\b|\bmultiplied\s+by\b", "*", normalized)
        normalized = re.sub(r"\bdivided\s+by\b", "/", normalized)
        normalized = re.sub(r"\bx\b", "*", normalized)

        # Check if only digits and basic operators remain
        if re.match(r"^[\d\s\+\-\*\/\.\(\)]+$", normalized) and any(op in normalized for op in "+-*/"):
            try:
                # Safe evaluation of basic numbers and arithmetic
                result = eval(normalized, {"__builtins__": None}, {})
                if isinstance(result, float) and result.is_integer():
                    result = int(result)
                return f"{query.rstrip('?').strip()} is {result}, boss."
            except Exception:
                pass
        return None

    def _offline_fallback(self, query: str) -> str:
        """Intelligent, witty local fallback when offline or no API key is available."""
        q = query.lower().strip()

        # Greetings
        if re.search(r"\b(?:hello|hi|hey|good\s+morning|good\s+evening|greetings)\b", q):
            return "Greetings, boss. All systems are operational and ready for your command."

        # How are you
        if "how are you" in q:
            return "Running at peak efficiency, boss. How can I assist you today?"

        # Identity
        if re.search(r"\b(?:who\s+are\s+you|what\s+are\s+you|your\s+name)\b", q):
            return "I am JARVIS, your personal voice assistant and task automation system, boss."

        # Capabilities
        if "what can you do" in q or "help" in q:
            return "I can control volume, open apps, take screenshots, lock your PC, search the web, and execute multi-action tasks, boss."

        # Thank you
        if "thank" in q:
            return "Always at your service, boss."

        # Default notice
        return (
            "I heard your question, boss. Set a GROQ_API_KEY or run Ollama locally "
            "to enable full conversational intelligence."
        )
