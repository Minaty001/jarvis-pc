"""OpenAI-compatible chat-completions client for the JARVIS brain.

Works against any OpenAI-compatible endpoint (Groq, NVIDIA NIM, OpenRouter,
Ollama, vLLM). Falls back to a local rule-based reply when no API key is
configured, so the assistant still functions offline.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from jarvis.config.settings import Settings

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "qwen/qwen3.8-27b"
PLACEHOLDER_MARKERS = ("your_", "here", "changeme", "xxx", "sk-or-")
MAX_RETRIES = 3
RETRYABLE_STATUS = (429, 500, 502, 503, 504)


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))


async def _chat_with_retry(client: httpx.AsyncClient, **kwargs: Any) -> httpx.Response:
    """POST with bounded exponential backoff for transient errors (429/5xx/timeouts)."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.post(**kwargs)
            response.raise_for_status()
            return response
        except Exception as exc:
            if attempt >= MAX_RETRIES or not _is_retryable(exc):
                raise
            delay = 2**attempt
            logger.warning("LLM call transient failure (attempt %s/%s): %s — retrying in %ss",
                           attempt + 1, MAX_RETRIES + 1, exc, delay)
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResult:
    content: str | None
    tool_calls: list[ToolCall]
    stop_reason: str


def _looks_like_placeholder(key: str | None) -> bool:
    if not key:
        return True
    lowered = key.lower()
    return any(m in lowered for m in PLACEHOLDER_MARKERS)


class LocalBrain:
    """Deterministic offline reply used when no LLM is configured."""

    def __init__(self, model: str = "local") -> None:
        self.model = model

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatResult:
        names = ", ".join(t["function"]["name"] for t in tools) if tools else "none"
        reply = (
            "At present my higher cognitive functions are not connected, sir — "
            f"no language model is configured. Configure JARVIS_LLM_API_KEY to arm them. "
            f"Meanwhile I can still operate {names or 'no tools'} on request."
        )
        return ChatResult(content=reply, tool_calls=[], stop_reason="stop")


class LLMClient:
    """Minimal OpenAI-compatible chat completions client."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/") or DEFAULT_BASE_URL
        self.api_key = api_key or None
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return not _looks_like_placeholder(self.api_key)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "LLMClient":
        if settings is None:
            settings = Settings()
        api_key = settings.llm_api_key
        return cls(
            base_url=settings.llm_base_url or DEFAULT_BASE_URL,
            api_key=None if _looks_like_placeholder(api_key) else api_key,
            model=settings.llm_model or DEFAULT_MODEL,
        )

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1500,
    ) -> ChatResult:
        if not self.available:
            return await LocalBrain(self.model).chat(messages, tools)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await _chat_with_retry(
                client,
                url=f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            data = response.json()

        choice = data["choices"][0]
        message = choice.get("message", {})
        finish = choice.get("finish_reason", "stop")

        tool_calls: list[ToolCall] = []
        for raw in message.get("tool_calls") or []:
            try:
                args = json.loads(raw["function"].get("arguments") or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append(
                ToolCall(
                    id=raw.get("id", ""),
                    name=raw["function"]["name"],
                    arguments=args if isinstance(args, dict) else {},
                )
            )

        return ChatResult(
            content=message.get("content"),
            tool_calls=tool_calls,
            stop_reason=finish,
        )