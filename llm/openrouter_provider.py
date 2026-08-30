"""OpenRouter Provider — Free model fallback."""

import json
import re
from typing import Optional

import httpx

from config.logger import get_logger
from config.settings import settings
from llm.base import LLMProvider, LLMRequest, LLMResponse

logger = get_logger("llm.openrouter")


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider for free model fallback."""

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def is_available(self) -> bool:
        return bool(settings.openrouter_api_key)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.is_available:
            return LLMResponse(text="", provider=self.name, model="unavailable")

        model = request.model or settings.openrouter_model
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{settings.openrouter_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://jarvis-pc.local",
                        "X-Title": "Jarvis PC",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": request.temperature,
                        "max_tokens": request.max_tokens,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                return self._parse_response(text, model)
        except Exception as e:
            logger.error("OpenRouter error: %s", e)
            return LLMResponse(text=f"OpenRouter error: {e}", provider=self.name, model=model)

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


openrouter_provider = OpenRouterProvider()
