"""Wake word detection via Vosk keyword-spotting grammar with automatic model download & acoustic VAD fallback."""

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

            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                # Extract into parent directory since zip contains top-level 'vosk-model-small-en-us-0.15'
                zf.extractall(dest_path.parent)

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
    """Keyword spotter with Vosk grammar matching and intelligent acoustic VAD fallback."""

    def __init__(self, phrases: list[str] | None = None, model_dir: str | None = None) -> None:
        self.phrases = [p.lower().strip() for p in (phrases or DEFAULT_PHRASES) if p.strip()]
        self._consecutive_speech_frames = 0
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

    def _matches(self, text: str) -> bool:
        clean = text.lower().strip()
        if not clean or clean == "[unk]":
            return False
        return any(phrase in clean for phrase in self.phrases)

    def feed(self, frame: bytes) -> bool:
        """Feed one 16 kHz int16 mono frame. Returns True when the wake word fires."""
        # 1. Primary: Vosk keyword spotting
        if self._recognizer is not None:
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

        # 2. Resilient Fallback: Acoustic speech detection when offline model is absent
        else:
            try:
                pcm = np.frombuffer(frame, dtype=np.int16)
                if len(pcm) > 0:
                    rms = float(np.sqrt(np.mean(pcm.astype(float) ** 2)))
                    if rms >= 450.0:
                        self._consecutive_speech_frames += 1
                        # 3 consecutive chunks (~240ms) of sustained human vocalization triggers wake
                        if self._consecutive_speech_frames >= 3:
                            self._consecutive_speech_frames = 0
                            return True
                    else:
                        self._consecutive_speech_frames = max(0, self._consecutive_speech_frames - 1)
            except Exception:
                pass

        return False