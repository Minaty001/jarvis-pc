"""
Speech-to-Text (STT) — faster-whisper on CPU.
Local Whisper inference for command recognition.
"""

from typing import Optional

import numpy as np

from config.logger import get_logger
from config.settings import settings

logger = get_logger("voice.stt")

try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False
    logger.warning("faster-whisper not installed. STT disabled.")


class WhisperSTT:
    """Local Whisper STT engine using faster-whisper."""

    def __init__(self):
        self._model: Optional[WhisperModel] = None
        self._loaded = False

    def load(self) -> bool:
        """Load the Whisper model."""
        if not HAS_WHISPER:
            return False

        try:
            logger.info("Loading Whisper model '%s' (device=%s, compute=%s)...",
                        settings.whisper_model, settings.whisper_device, settings.whisper_compute_type)
            self._model = WhisperModel(
                settings.whisper_model,
                device=settings.whisper_device,
                compute_type=settings.whisper_compute_type,
            )
            self._loaded = True
            logger.info("Whisper model loaded successfully")
            return True
        except Exception as e:
            logger.error("Failed to load Whisper model: %s", e)
            return False

    def transcribe(self, audio: np.ndarray, language: str = "en") -> str:
        """Transcribe audio array to text."""
        if not self._loaded or self._model is None:
            logger.error("Whisper model not loaded")
            return ""

        try:
            audio_float = audio.astype(np.float32)
            if audio_float.max() > 1.0:
                audio_float = audio_float / 32768.0

            segments, info = self._model.transcribe(
                audio_float,
                language=language,
                beam_size=3,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            text_parts = [segment.text for segment in segments]
            text = " ".join(text_parts).strip()

            if text:
                logger.info("STT: '%s' (lang=%.2f)", text, info.language_probability)
            return text

        except Exception as e:
            logger.error("STT error: %s", e)
            return ""

    def transcribe_file(self, file_path: str, language: str = "en") -> str:
        """Transcribe an audio file."""
        if not self._loaded or self._model is None:
            return ""
        try:
            segments, info = self._model.transcribe(
                file_path,
                language=language,
                beam_size=3,
            )
            return " ".join(s.text for s in segments).strip()
        except Exception as e:
            logger.error("STT file error: %s", e)
            return ""

    @property
    def is_loaded(self) -> bool:
        return self._loaded


whisper_stt = WhisperSTT()
