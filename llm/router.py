"""
LLM Router — Task-based provider selection.
Routes to the best provider based on task type.
"""

from config.logger import get_logger
from llm.groq_provider import groq_provider
from llm.nim_provider import nim_provider
from llm.openrouter_provider import openrouter_provider
from llm.zen_provider import zen_provider

logger = get_logger("llm.router")

# Keywords that indicate task type
CODE_KEYWORDS = {
    "code", "function", "class", "debug", "git", "docker", "ssh",
    "python", "javascript", "script", "error", "exception", "compile",
    "build", "test", "lint", "format", "refactor", "implement",
    "write a program", "write code", "coding", "programming",
}

VISION_KEYWORDS = {
    "look at", "screenshot", "image", "visual", "what's on",
    "what do you see", "analyze image", "describe the screen",
    "show me", "read this image", "ocr",
}


def classify_task(text: str) -> str:
    """Classify user intent to route to the right provider."""
    text_lower = text.lower()

    if any(kw in text_lower for kw in CODE_KEYWORDS):
        return "code"

    if any(kw in text_lower for kw in VISION_KEYWORDS):
        return "vision"

    return "chat"


def get_provider_for_task(task_type: str):
    """Return the best provider for a given task type."""
    providers = {
        "code": zen_provider,
        "vision": nim_provider,
        "chat": groq_provider,
    }
    provider = providers.get(task_type, groq_provider)

    if provider.is_available:
        return provider

    # Fallback chain
    for fallback in [groq_provider, nim_provider, openrouter_provider]:
        if fallback.is_available:
            logger.info("Primary provider unavailable, falling back to %s", fallback.name)
            return fallback

    return groq_provider


def get_fallback_chain():
    """Return ordered list of available providers for failover."""
    chain = []
    for p in [groq_provider, nim_provider, zen_provider, openrouter_provider]:
        if p.is_available:
            chain.append(p)
    return chain
