"""
LLM Gateway — Unified interface for all LLM operations.
Handles provider selection, failover, and response parsing.
"""

from typing import Any, Optional

from config.logger import get_logger
from llm.base import LLMRequest, LLMResponse
from llm.router import classify_task, get_fallback_chain, get_provider_for_task

logger = get_logger("llm.gateway")


class LLMGateway:
    """Main LLM gateway with task-based routing and failover."""

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        task_type: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        if task_type is None:
            task_type = classify_task(prompt)

        provider = get_provider_for_task(task_type)
        request = LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
        )

        logger.info("Routing to %s (task: %s)", provider.name, task_type)

        try:
            response = await provider.generate(request)
            if response.text:
                return response
        except Exception as e:
            logger.error("Provider %s failed: %s", provider.name, e)

        # Failover chain
        for fallback in get_fallback_chain():
            if fallback.name == provider.name:
                continue
            try:
                logger.info("Failover to %s", fallback.name)
                response = await fallback.generate(request)
                if response.text:
                    return response
            except Exception as e:
                logger.error("Fallback %s failed: %s", fallback.name, e)

        return self._local_fallback(prompt)

    def _local_fallback(self, prompt: str) -> LLMResponse:
        """Last-resort local responses when all providers fail."""
        p = prompt.lower().strip()
        responses = {
            ("hello", "hey", "hi", "suno"): "Hello! I am Jarvis. How can I assist you?",
            ("who are you", "what is your name"): "I am Jarvis, your personal AI assistant.",
            ("how are you",): "All systems operating at peak performance!",
            ("what can you do", "help", "features"): "I can control your PC, open apps, search the web, and assist with tasks.",
            ("thank",): "You are welcome!",
            ("bye", "good night"): "Goodbye! Let me know if you need anything.",
        }
        for keywords, response in responses.items():
            if any(k in p for k in keywords):
                return LLMResponse(text=response, action="answer", provider="local", model="rule-based", confidence=1.0)
        return LLMResponse(
            text=f"I processed your request. All cloud providers are currently unavailable.",
            action="answer",
            provider="local",
            model="rule-based",
            confidence=0.5,
        )


llm_gateway = LLMGateway()
