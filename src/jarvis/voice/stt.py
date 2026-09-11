"""Speech-to-text: Groq Whisper (accurate, online) with Vosk offline fallback."""

import json
import logging
import os

import httpx

from jarvis.voice.audio import pcm_to_wav_bytes

logger = logging.getLogger(__name__)

_GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def groq_transcribe(wav_bytes: bytes) -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except (ImportError, OSError):  # pragma: no cover - dotenv always present here
        pass
    api_key = os.getenv("JARVIS_LLM_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("No GROQ API key found (set JARVIS_LLM_API_KEY or GROQ_API_KEY).")
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            _GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": ("audio.wav", wav_bytes, "audio/wav")},
            data={"model": "whisper-large-v3-turbo"},
        )
    resp.raise_for_status()
    return resp.json()["text"].strip()


def vosk_transcribe(wav_bytes: bytes, model_dir: str | None = None) -> str:
    """Offline transcription via Vosk (expects 16 kHz mono WAV)."""
    import io
    import wave

    from vosk import KaldiRecognizer, Model

    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        if w.getframerate() != 16000:
            raise ValueError("Vosk requires 16 kHz audio; resample first.")
        pcm = w.readframes(w.getnframes())
    rec = KaldiRecognizer(Model(model_dir or _default_model_dir()), 16000)
    rec.AcceptWaveform(pcm)
    return json.loads(rec.FinalResult()).get("text", "").strip()


def transcribe(wav_bytes: bytes) -> str:
    """Transcribe WAV bytes. Tries Groq Whisper first, falls back to Vosk."""
    try:
        return groq_transcribe(wav_bytes)
    except Exception as exc:
        logger.debug("Groq transcribe failed (%s); falling back to Vosk", exc)
    return vosk_transcribe(wav_bytes)


def wav_at_16k(pcm, sample_rate: int) -> bytes:
    """Wrap PCM in a 16 kHz mono WAV (for Vosk)."""
    from jarvis.voice.audio import resample_16k

    return pcm_to_wav_bytes(resample_16k(pcm, sample_rate), 16000)


def _default_model_dir() -> str:
    return os.path.expanduser("~/.local/share/jarvis/models/vosk-model-small-en-us-0.15")