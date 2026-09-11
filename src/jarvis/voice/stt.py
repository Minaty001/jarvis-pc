"""Speech-to-text: Groq Whisper (accurate, online) with Vosk offline fallback."""

import json
import logging
import os

import httpx

from jarvis.voice.audio import pcm_to_wav_bytes

logger = logging.getLogger(__name__)

_GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


PLACEHOLDER_MARKERS = ("your_", "here", "changeme", "xxx", "sk-or-", "test_key")


def _is_valid_api_key(key: str | None) -> bool:
    if not key or len(key.strip()) < 8:
        return False
    key_lower = key.lower()
    return not any(marker in key_lower for marker in PLACEHOLDER_MARKERS)


def groq_transcribe(wav_bytes: bytes) -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except (ImportError, OSError):  # pragma: no cover
        pass
    api_key = os.getenv("JARVIS_LLM_API_KEY") or os.getenv("GROQ_API_KEY")
    if not _is_valid_api_key(api_key):
        raise RuntimeError("No valid GROQ API key found (set JARVIS_LLM_API_KEY or GROQ_API_KEY).")
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            _GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": ("audio.wav", wav_bytes, "audio/wav")},
            data={"model": "whisper-large-v3-turbo"},
        )
    resp.raise_for_status()
    return resp.json()["text"].strip()


async def groq_transcribe_async(wav_bytes: bytes) -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except (ImportError, OSError):  # pragma: no cover
        pass
    api_key = os.getenv("JARVIS_LLM_API_KEY") or os.getenv("GROQ_API_KEY")
    if not _is_valid_api_key(api_key):
        raise RuntimeError("No valid GROQ API key found.")
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            _GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": ("audio.wav", wav_bytes, "audio/wav")},
            data={"model": "whisper-large-v3-turbo"},
        )
    resp.raise_for_status()
    return resp.json()["text"].strip()


def vosk_transcribe(wav_bytes: bytes, model_dir: str | None = None) -> str:
    """Offline transcription via Vosk using cached model and chunked processing."""
    import io
    import wave

    from vosk import KaldiRecognizer
    from jarvis.voice.wake_word import get_model

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            if w.getframerate() != 16000:
                raise ValueError("Vosk requires 16 kHz audio; resample first.")
            pcm = w.readframes(w.getnframes())
        model = get_model(model_dir or _default_model_dir())
        rec = KaldiRecognizer(model, 16000)
        rec.SetWords(True)

        chunk_size = 4000
        for i in range(0, len(pcm), chunk_size):
            rec.AcceptWaveform(pcm[i:i + chunk_size])

        final = json.loads(rec.FinalResult())
        return final.get("text", "").strip()
    except Exception as exc:
        logger.warning("Vosk transcription error: %s", exc)
        return ""


def transcribe(wav_bytes: bytes) -> str:
    """Transcribe WAV bytes. Tries Groq Whisper first, falls back to Vosk."""
    try:
        return groq_transcribe(wav_bytes)
    except Exception as exc:
        logger.debug("Groq transcribe unavailable (%s); falling back to Vosk", exc)
    return vosk_transcribe(wav_bytes)


async def transcribe_async(wav_bytes: bytes) -> str:
    """Async transcription of WAV bytes with Groq -> Vosk fallback."""
    try:
        return await groq_transcribe_async(wav_bytes)
    except Exception as exc:
        logger.debug("Async Groq transcribe unavailable (%s); falling back to Vosk", exc)
    return vosk_transcribe(wav_bytes)


def wav_at_16k(pcm, sample_rate: int) -> bytes:
    """Wrap PCM in a 16 kHz mono WAV (for Vosk)."""
    from jarvis.voice.audio import resample_16k

    return pcm_to_wav_bytes(resample_16k(pcm, sample_rate), 16000)


def transcribe_pcm(pcm, sample_rate: int = 16000) -> str:
    """Transcribe raw int16 PCM numpy array into text."""
    return transcribe(wav_at_16k(pcm, sample_rate))


def _default_model_dir() -> str:
    return os.path.expanduser("~/.local/share/jarvis/models/vosk-model-small-en-us-0.15")