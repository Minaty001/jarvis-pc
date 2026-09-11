"""Wake word detection via Vosk keyword-spotting grammar (offline, 16 kHz int16)."""

import json
import os

from vosk import KaldiRecognizer, Model

DEFAULT_PHRASES = ["hey jarvis", "jarvis"]


def default_model_dir() -> str:
    return os.path.expanduser("~/.local/share/jarvis/models/vosk-model-small-en-us-0.15")


class WakeWordDetector:
    def __init__(self, phrases: list[str] | None = None, model_dir: str | None = None):
        self.phrases = phrases or list(DEFAULT_PHRASES)
        self._model = Model(model_dir or default_model_dir())
        self._recognizer = KaldiRecognizer(self._model, 16000, json.dumps(self.phrases))

    def feed(self, frame: bytes) -> bool:
        """Feed one 16 kHz int16 mono frame. Returns True when the wake word fires."""
        done = self._recognizer.AcceptWaveform(frame)
        if done:
            text = json.loads(self._recognizer.Result()).get("text", "")
            self._recognizer = KaldiRecognizer(self._model, 16000, json.dumps(self.phrases))
            if text.strip():
                return True
        return False