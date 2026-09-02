"""Typed Pydantic configuration settings for JARVIS."""

from functools import lru_cache
from pydantic import Field
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
    max_request_bytes: int = Field(default=DEFAULT_MAX_REQUEST_BYTES, ge=1024)
    command_timeout_seconds: float = Field(
        default=DEFAULT_COMMAND_TIMEOUT_SECONDS, gt=0, le=300
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
