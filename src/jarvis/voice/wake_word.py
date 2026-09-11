"""Wake word detection via Vosk keyword-spotting grammar (offline, 16 kHz int16)."""

import json
import logging
import os
from typing import Dict

from vosk import KaldiRecognizer, Model, SetLogLevel

logger = logging.getLogger(__name__)

DEFAULT_PHRASES = ["hey jarvis", "jarvis"]
_MODEL_CACHE: Dict[str, Model] = {}


def default_model_dir() -> str:
    return os.path.expanduser("~/.local/share/jarvis/models/vosk-model-small-en-us-0.15")


def get_model(model_dir: str | None = None) -> Model:
    """Return cached Vosk Model instance to prevent expensive reloading."""
    path = os.path.expanduser(model_dir or default_model_dir())
    if path not in _MODEL_CACHE:
        SetLogLevel(-1)
        _MODEL_CACHE[path] = Model(path)
    return _MODEL_CACHE[path]


class WakeWordDetector:
    def __init__(self, phrases: list[str] | None = None, model_dir: str | None = None):
        self.phrases = [p.lower().strip() for p in (phrases or DEFAULT_PHRASES) if p.strip()]
        self._model = get_model(model_dir)
        # Vosk grammar requires [unk] to filter out words and noise outside the target vocabulary
        grammar = list(self.phrases) + ["[unk]"]
        self._recognizer = KaldiRecognizer(self._model, 16000, json.dumps(grammar))

    def _matches(self, text: str) -> bool:
        clean = text.lower().strip()
        if not clean or clean == "[unk]":
            return False
        return any(phrase in clean for phrase in self.phrases)

    def feed(self, frame: bytes) -> bool:
        """Feed one 16 kHz int16 mono frame. Returns True when the wake word fires."""
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
        return False