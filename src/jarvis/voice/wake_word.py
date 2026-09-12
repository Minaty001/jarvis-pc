"""Wake word detection via Vosk keyword-spotting grammar (offline, 16 kHz int16)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

try:
    from vosk import KaldiRecognizer, Model, SetLogLevel
    VOSK_AVAILABLE = True
except ImportError:
    KaldiRecognizer = None  # type: ignore
    Model = None  # type: ignore
    SetLogLevel = None  # type: ignore
    VOSK_AVAILABLE = False

logger = logging.getLogger(__name__)

DEFAULT_PHRASES = ["hey jarvis", "jarvis"]
_MODEL_CACHE: Dict[str, Any] = {}


def default_model_dir() -> str:
    return os.path.expanduser("~/.local/share/jarvis/models/vosk-model-small-en-us-0.15")


def get_model(model_dir: str | None = None) -> Optional[Any]:
    """Return cached Vosk Model instance to prevent expensive reloading."""
    if not VOSK_AVAILABLE or Model is None:
        return None
    path = os.path.expanduser(model_dir or default_model_dir())
    if path not in _MODEL_CACHE:
        try:
            if SetLogLevel is not None:
                SetLogLevel(-1)
            _MODEL_CACHE[path] = Model(path)
        except Exception as exc:
            logger.debug("Could not load Vosk model at %s: %s", path, exc)
            return None
    return _MODEL_CACHE.get(path)


class WakeWordDetector:
    def __init__(self, phrases: list[str] | None = None, model_dir: str | None = None) -> None:
        self.phrases = [p.lower().strip() for p in (phrases or DEFAULT_PHRASES) if p.strip()]
        self._model = get_model(model_dir)
        if self._model is not None and KaldiRecognizer is not None:
            try:
                # Vosk grammar requires [unk] to filter out words and noise outside the target vocabulary
                grammar = list(self.phrases) + ["[unk]"]
                self._recognizer = KaldiRecognizer(self._model, 16000, json.dumps(grammar))
            except Exception as ex:
                logger.debug("Could not initialize Vosk recognizer: %s", ex)
                self._recognizer = None
        else:
            self._recognizer = None

    def _matches(self, text: str) -> bool:
        clean = text.lower().strip()
        if not clean or clean == "[unk]":
            return False
        return any(phrase in clean for phrase in self.phrases)

    def feed(self, frame: bytes) -> bool:
        """Feed one 16 kHz int16 mono frame. Returns True when the wake word fires."""
        if self._recognizer is None:
            return False
        try:
            if self._recognizer.AcceptWaveform(frame):
                text = json.loads(self._recognizer.Result()).get("text", "")
                if self._matches(text):
                    self._recognizer.Reset()
                    return True
            else:
                partial = json.loads(self._recognizer.PartialResult()).get("partial", "")
                if self._matches(partial):
                    self._recognizer.Reset()
                    return True
        except Exception as ex:
            logger.debug("Wake word feed error: %s", ex)
        return False