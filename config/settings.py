"""Jarvis PC Settings — Pydantic BaseSettings."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
WAKEWORD_DIR = ASSETS_DIR / "wakeword"
DATA_DIR = PROJECT_ROOT / "data"

DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    """All Jarvis configuration in one place. Reads from .env file."""

    # === Groq (Normal Conversation) ===
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = "qwen/qwen3.8-27b"

    # === NVIDIA NIM (Visualization/Vision) ===
    nvidia_api_key: str = Field(default="", alias="NVIDIA_API_KEY")
    nvidia_model: str = "nvidia/nemotron-nano-12b-v2-vl"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    # === OpenCode Zen (Coding Tasks) ===
    zen_api_key: str = Field(default="", alias="ZEN_API_KEY")
    zen_model: str = "zen-code"
    zen_base_url: str = "https://api.opencode.ai/v1"

    # === OpenRouter (Fallback) ===
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = "openrouter/free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # === Voice Settings ===
    jarvis_voice: str = Field(default="en-US-GuyNeural", alias="JARVIS_VOICE")
    jarvis_rate: str = "+0%"
    jarvis_volume: str = "+0%"
    wake_threshold: float = Field(default=0.5, alias="JARVIS_WAKE_THRESHOLD")
    sample_rate: int = 16000
    vad_threshold: float = 0.5

    # === Whisper STT ===
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # === Camera ===
    camera_index: int = 0
    camera_photo_dir: str = "data/camera"

    # === Smart Home (Optional) ===
    home_assistant_url: str = Field(default="", alias="HOME_ASSISTANT_URL")
    home_assistant_token: str = Field(default="", alias="HOME_ASSISTANT_TOKEN")

    # === Paths ===
    assets_dir: Path = ASSETS_DIR
    wakeword_dir: Path = WAKEWORD_DIR
    data_dir: Path = DATA_DIR

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "case_sensitive": False,
    }


settings = Settings()
