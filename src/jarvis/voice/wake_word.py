"""Wake word detection via Vosk keyword-spotting grammar with automatic model download."""

from __future__ import annotations

import io
import json
import logging
import os
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional
import urllib.request
import zipfile

import numpy as np

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
_DOWNLOAD_LOCK = threading.Lock()
_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"


def default_model_dir() -> str:
    return os.path.expanduser("~/.local/share/jarvis/models/vosk-model-small-en-us-0.15")


def download_vosk_model(target_dir: Optional[str] = None) -> bool:
    """Download and extract the lightweight Vosk English model (~40MB)."""
    dest_path = Path(os.path.expanduser(target_dir or default_model_dir()))
    if dest_path.exists() and (dest_path / "am").exists():
        return True

    with _DOWNLOAD_LOCK:
        if dest_path.exists() and (dest_path / "am").exists():
            return True
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info("Downloading Vosk offline acoustic model from %s...", _MODEL_URL)
            req = urllib.request.Request(_MODEL_URL, headers={"User-Agent": "JARVIS-Voice-Setup/1.0"})
            with urllib.request.urlopen(req, timeout=30.0) as resp:  # nosec B310
                zip_data = resp.read()

            target_parent = dest_path.parent.resolve()
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                for member in zf.infolist():
                    member_path = (target_parent / member.filename).resolve()
                    if not str(member_path).startswith(str(target_parent)):
                        raise ValueError(f"Malicious zip member path detected: {member.filename}")
                # Extract into parent directory since zip contains top-level 'vosk-model-small-en-us-0.15'
                zf.extractall(target_parent)

            logger.info("Vosk model successfully extracted to %s", dest_path)
            return True
        except Exception as exc:
            logger.debug("Failed to download Vosk model: %s", exc)
            return False


def get_model(model_dir: str | None = None) -> Optional[Any]:
    """Return cached Vosk Model instance to prevent expensive reloading."""
    if not VOSK_AVAILABLE or Model is None:
        return None
    path_str = os.path.expanduser(model_dir or default_model_dir())
    path = Path(path_str)

    if path_str not in _MODEL_CACHE:
        if not path.exists():
            # Try to trigger asynchronous/sync download if missing
            download_vosk_model(path_str)

        if path.exists():
            try:
                if SetLogLevel is not None:
                    SetLogLevel(-1)
                _MODEL_CACHE[path_str] = Model(path_str)
            except Exception as exc:
                logger.debug("Could not load Vosk model at %s: %s", path_str, exc)
                return None
        else:
            return None

    return _MODEL_CACHE.get(path_str)


class WakeWordDetector:
    """Keyword spotter with Vosk grammar matching."""

    def __init__(self, phrases: list[str] | None = None, model_dir: str | None = None) -> None:
        self.phrases = [p.lower().strip() for p in (phrases or DEFAULT_PHRASES) if p.strip()]
        self._model = get_model(model_dir)

        if self._model is not None and KaldiRecognizer is not None:
            try:
                grammar = list(self.phrases) + ["[unk]"]
                self._recognizer = KaldiRecognizer(self._model, 16000, json.dumps(grammar))
            except Exception as ex:
                logger.debug("Could not initialize Vosk recognizer: %s", ex)
                self._recognizer = None
        else:
            self._recognizer = None

    @property
    def is_available(self) -> bool:
        """Return True if wake word model and recognizer are initialized."""
        return self._recognizer is not None

    def _matches(self, text: str) -> bool:
        clean = text.lower().strip()
        if not clean or clean == "[unk]":
            return False
        return any(phrase in clean for phrase in self.phrases)

    def feed(self, frame: bytes) -> bool:
        """Feed one 16 kHz int16 mono frame. Returns True when the wake word fires."""
        if self._recognizer is None:
            # Fail closed: never trigger wake word on noise when speech recognizer is unavailable
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