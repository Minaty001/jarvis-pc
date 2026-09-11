"""Offline tests for the voice package — all use the bundled 16k speech fixture."""

import wave
from pathlib import Path

import numpy as np
import pytest

from jarvis.voice import stt, vad
from jarvis.voice.audio import pcm_to_wav_bytes, resample_16k, to_mono
from jarvis.voice.wake_word import WakeWordDetector

FIXTURE = Path(__file__).parent / "data" / "hey_jarvis.wav"


@pytest.fixture(scope="module")
def speech_wav() -> bytes:
    data = (FIXTURE).read_bytes()
    assert data, "speech fixture missing"
    return data


def _wav_pcm(wav_bytes: bytes) -> np.ndarray:
    import io

    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")


def test_vad_speech_detects_speech_fixture(speech_wav):
    assert vad.is_speech(_wav_pcm(speech_wav))
    assert not vad.is_speech(np.zeros(1280, dtype="i2"), threshold=300)


def test_audio_helpers_build_valid_wav():
    pcm = np.arange(0, 320, 1, dtype="i2")
    wav = pcm_to_wav_bytes(pcm, 16000)
    with wave.open(io := __import__("io").BytesIO(wav), "rb") as w:
        assert w.getframerate() == 16000
        assert w.readframes(w.getnframes()) == pcm.tobytes()
    io.close()


def test_resample_preserves_length_and_type():
    pcm = np.sin(np.linspace(0, 10, 44000)).astype("<i2")
    mono = resample_16k(pcm, 44100)
    assert abs(len(mono) / 16000 - 1.0) < 0.05
    assert mono.dtype == np.dtype("<i2")


def test_wake_word_fires_on_fixture(speech_wav):
    pcm = _wav_pcm(speech_wav)
    det = WakeWordDetector()
    fired = any(det.feed(pcm[i : i + 1280].tobytes()) for i in range(0, len(pcm), 1280))
    assert fired, "wake word not detected on 'Hey Jarvis' fixture"


def test_vosk_transcribe_fixture(speech_wav):
    text = stt.vosk_transcribe(speech_wav)
    assert "jarvis" in text.lower(), f"unexpected transcript: {text!r}"


def test_transcribe_falls_back_to_vosk(speech_wav, monkeypatch):
    # Ensure Groq fails so it tests fallback to Vosk
    monkeypatch.delenv("JARVIS_LLM_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    text = stt.transcribe(speech_wav)
    assert "jarvis" in text.lower()


def test_tts_speak_fallback_on_error():
    from unittest.mock import patch
    from jarvis.voice import tts

    with patch("jarvis.voice.tts.synthesize", side_effect=RuntimeError("offline")):
        with patch("jarvis.voice.tts.subprocess.run") as mock_run:
            res = tts.speak("Test speech")
            assert res == b""
            assert mock_run.called