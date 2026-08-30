"""Base LLM Provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LLMRequest:
    prompt: str
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1024
    tools: Optional[list[dict[str, Any]]] = None


@dataclass
class LLMResponse:
    text: str = ""
    action: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    provider: str = "unknown"
    model: str = "unknown"
    tool_calls: Optional[list[dict[str, Any]]] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        ...
