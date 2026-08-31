"""Groq LLM Provider — Fast inference for normal conversation."""

import json
import re
from typing import Optional

from config.logger import get_logger
from config.settings import settings
from llm.base import LLMProvider, LLMRequest, LLMResponse

logger = get_logger("llm.groq")

try:
    from groq import AsyncGroq
    HAS_GROQ = True
except ImportError:
    AsyncGroq = None  # type: ignore
    HAS_GROQ = False


class GroqProvider(LLMProvider):
    """Groq provider for fast conversational inference."""

    def __init__(self):
        self._client: Optional[AsyncGroq] = None

    @property
    def name(self) -> str:
        return "groq"

    @property
    def is_available(self) -> bool:
        return HAS_GROQ and bool(settings.groq_api_key)

    def _get_client(self) -> AsyncGroq:
        if self._client is None:
            self._client = AsyncGroq(api_key=settings.groq_api_key)
        return self._client

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.is_available:
            return LLMResponse(text="", provider=self.name, model="unavailable")

        model = request.model or settings.groq_model
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            text = response.choices[0].message.content or ""
            return self._parse_response(text, model)
        except Exception as e:
            logger.error("Groq error: %s", e)
            return LLMResponse(text=f"Groq error: {e}", provider=self.name, model=model)

    def _parse_response(self, text: str, model: str) -> LLMResponse:
        json_match = re.search(r'\{[^{}]*"action"[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return LLMResponse(
                    text=text,
                    action=data.get("action"),
                    parameters=data.get("parameters", {}),
                    confidence=data.get("confidence", 0.9),
                    provider=self.name,
                    model=model,
                )
            except json.JSONDecodeError:
                pass
        return LLMResponse(text=text, action="answer", provider=self.name, model=model, confidence=0.95)


groq_provider = GroqProvider()
