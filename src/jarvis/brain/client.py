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


def _parse_chat_response(data: dict[str, Any]) -> ChatResult:
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


class LLMClient:
    """Minimal OpenAI-compatible chat completions client with local fallback."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        timeout: float = 60.0,
        local_base_url: str = "http://localhost:11434/v1",
        local_model: str = "qwen2.5:7b",
        local_enabled: bool = True,
        local_timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/") or DEFAULT_BASE_URL
        self.api_key = api_key or None
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout
        self.local_base_url = (local_base_url or "http://localhost:11434/v1").rstrip("/")
        self.local_model = local_model or "qwen2.5:7b"
        self.local_enabled = local_enabled
        self.local_timeout = local_timeout

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
            timeout=settings.command_timeout_seconds,
            local_base_url=settings.local_llm_base_url,
            local_model=settings.local_llm_model,
            local_enabled=settings.local_llm_enabled,
            local_timeout=settings.local_llm_timeout,
        )

    async def _call_openai_endpoint(
        self,
        base_url: str,
        model: str,
        api_key: str | None,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1500,
        timeout: float = 60.0,
        retry: bool = True,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            if retry:
                response = await _chat_with_retry(
                    client,
                    url=f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
            else:
                response = await client.post(
                    url=f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
            data = response.json()

        return _parse_chat_response(data)

    async def _try_local_fallback(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1500,
    ) -> ChatResult | None:
        if not self.local_enabled:
            return None
        try:
            logger.info("Routing query to local LLM (%s at %s)...", self.local_model, self.local_base_url)
            return await self._call_openai_endpoint(
                base_url=self.local_base_url,
                model=self.local_model,
                api_key=None,
                messages=messages,
                tools=tools,
                max_tokens=max_tokens,
                timeout=self.local_timeout,
                retry=False,
            )
        except Exception as exc:
            logger.debug("Local LLM fallback failed: %s", exc)
            return None

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1500,
    ) -> ChatResult:
        # Case 1: Cloud API key is configured
        if self.available:
            try:
                return await self._call_openai_endpoint(
                    base_url=self.base_url,
                    model=self.model,
                    api_key=self.api_key,
                    messages=messages,
                    tools=tools,
                    max_tokens=max_tokens,
                    timeout=self.timeout,
                    retry=True,
                )
            except Exception as exc:
                logger.warning(
                    "Primary LLM call failed (%s). Attempting local offline fallback...", exc
                )
                local_res = await self._try_local_fallback(messages, tools, max_tokens)
                if local_res is not None:
                    return local_res
                return await LocalBrain(self.model).chat(messages, tools)

        # Case 2: Cloud API key is not configured — try local LLM directly
        local_res = await self._try_local_fallback(messages, tools, max_tokens)
        if local_res is not None:
            return local_res

        return await LocalBrain(self.model).chat(messages, tools)

    async def check_health(self) -> dict[str, Any]:
        """Check availability and latency of cloud and local LLM endpoints."""
        status: dict[str, Any] = {
            "cloud": {
                "available": self.available,
                "base_url": self.base_url,
                "model": self.model,
            },
            "local": {
                "enabled": self.local_enabled,
                "base_url": self.local_base_url,
                "model": self.local_model,
                "reachable": False,
            },
            "active_mode": "offline_brain",
        }

        if self.local_enabled:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"{self.local_base_url}/models")
                    if resp.status_code == 200:
                        status["local"]["reachable"] = True
            except Exception:
                status["local"]["reachable"] = False

        if self.available:
            status["active_mode"] = "cloud"
        elif status["local"]["reachable"]:
            status["active_mode"] = "local"
        else:
            status["active_mode"] = "offline_brain"

        return status