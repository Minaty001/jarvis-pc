"""Configuration and environment management for JARVIS."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional


def _load_dotenv_if_exists() -> None:
    """Load key-value pairs from .env if present in project root."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            clean = line.strip()
            if clean and not clean.startswith("#") and "=" in clean:
                k, v = clean.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        pass


_load_dotenv_if_exists()


@dataclass
class LLMConfig:
    """LLM provider and connection parameters."""
    provider: str
    api_key: Optional[str]
    base_url: str
    model: str
    timeout_seconds: float = 8.0


def get_llm_config() -> LLMConfig:
    """Detect and configure LLM endpoint from environment variables."""
    # Direct custom overrides
    custom_key = os.getenv("JARVIS_LLM_API_KEY")
    custom_url = os.getenv("JARVIS_LLM_BASE_URL")
    custom_model = os.getenv("JARVIS_LLM_MODEL")

    if custom_url:
        return LLMConfig(
            provider="custom",
            api_key=custom_key,
            base_url=custom_url.rstrip("/"),
            model=custom_model or "default",
        )

    # 1. Groq (Ultra-low latency for voice)
    groq_key = custom_key if (custom_key and custom_key.startswith("gsk_")) else os.getenv("GROQ_API_KEY")
    if groq_key:
        return LLMConfig(
            provider="groq",
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1",
            model=custom_model or "llama-3.1-8b-instant",
        )

    # 2. OpenRouter
    openrouter_key = custom_key if (custom_key and custom_key.startswith("sk-or-")) else os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        return LLMConfig(
            provider="openrouter",
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            model=custom_model or "meta-llama/llama-3.1-8b-instruct:free",
        )

    # 3. Gemini OpenAI-compatible endpoint
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        return LLMConfig(
            provider="gemini",
            api_key=gemini_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            model=custom_model or "gemini-2.0-flash",
        )

    # 4. Standard OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        return LLMConfig(
            provider="openai",
            api_key=openai_key,
            base_url="https://api.openai.com/v1",
            model=custom_model or "gpt-4o-mini",
        )

    # 5. Default fallback to local Ollama or offline
    return LLMConfig(
        provider="ollama",
        api_key=custom_key or "ollama",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").rstrip("/"),
        model=custom_model or "llama3.2",
    )
