"""Typed Pydantic configuration settings for JARVIS."""

from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from jarvis.config.defaults import (
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    DEFAULT_ENVIRONMENT,
    DEFAULT_HOST,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_REQUEST_BYTES,
    DEFAULT_PORT,
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables or defaults."""

    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",
        env_file=".env",
        extra="ignore",
    )

    environment: str = DEFAULT_ENVIRONMENT
    host: str = DEFAULT_HOST
    port: int = Field(default=DEFAULT_PORT, ge=1, le=65535)
    log_level: str = DEFAULT_LOG_LEVEL
    api_token: str | None = None
    confirmation_secret: str | None = None
    max_request_bytes: int = Field(default=DEFAULT_MAX_REQUEST_BYTES, ge=1024)
    command_timeout_seconds: float = Field(
        default=DEFAULT_COMMAND_TIMEOUT_SECONDS, gt=0, le=300
    )
    llm_base_url: str | None = None
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "JARVIS_LLM_API_KEY", "LLM_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"
        ),
    )
    llm_model: str | None = None
    voice: str = "en-US-GuyNeural"
    telegram_token: str | None = None
    telegram_allowed_chats: str | None = None
    proactive_ram_threshold: float = Field(default=85.0, ge=10.0, le=100.0)
    proactive_disk_threshold: float = Field(default=90.0, ge=10.0, le=100.0)
    proactive_cpu_threshold: float = Field(default=90.0, ge=10.0, le=100.0)
    proactive_battery_threshold: float = Field(default=15.0, ge=1.0, le=100.0)
    proactive_interval: float = Field(default=30.0, ge=5.0, le=600.0)
    local_llm_enabled: bool = True
    local_llm_base_url: str = "http://localhost:11434/v1"
    local_llm_model: str = "qwen2.5:7b"
    local_llm_timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    vision_model: str = "llama-3.2-11b-vision-preview"
    local_vision_model: str = "llama3.2-vision"
    voice_barge_in: bool = True
    voice_barge_in_mode: str = "vad_and_wake"
    voice_barge_in_sensitivity: float = Field(default=1.6, ge=1.0, le=5.0)
    default_location: str = "auto"
    morning_briefing_time: str = "08:00"
    briefing_spoken: bool = True
    voice_profile: str = "british_butler"
    voice_rate: str = "+0%"
    voice_pitch: str = "+0Hz"
    auto_wake_word: bool = True
    wake_phrases: str = "hey jarvis,jarvis"
    wake_ack_phrase: str = "Yes, sir?"
    wake_followup_timeout: float = Field(default=6.0, ge=0.1, le=60.0)
    wake_vad_threshold: int = Field(default=350, ge=100, le=2000)
    knowledge_dirs: str = "~/Documents,~/Notes"
    knowledge_db_path: str | None = None
    knowledge_chunk_size: int = Field(default=500, ge=50, le=2000)
    knowledge_chunk_overlap: int = Field(default=100, ge=0, le=500)
    knowledge_auto_index: bool = True


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
