"""Text-to-speech via edge-tts neural voices, with spd-say fallback if offline."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess  # nosec B404

try:
    import edge_tts
except ImportError:
    edge_tts = None  # type: ignore

from jarvis.voice.audio import decode_mp3, pcm_to_wav_bytes, to_mono

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "en-US-GuyNeural"


def synthesize(text: str, voice: str = DEFAULT_VOICE, timeout: float = 30.0) -> bytes:
    """Synthesize speech to MP3 bytes via edge-tts (Microsoft neural voices)."""
    if edge_tts is None:
        raise RuntimeError("edge-tts library is not installed or available.")

    async def _stream():
        communicate = edge_tts.Communicate(text, voice)
        data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                data += chunk["data"]
        return data

    return asyncio.run(asyncio.wait_for(_stream(), timeout))


def speak(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Speak `text` through the default audio output.

    Returns decoded WAV bytes. Falls back to spd-say when edge-tts is
    unavailable or offline.
    """
    try:
        mp3 = synthesize(text, voice)
        import sounddevice as sd

        pcm, sample_rate, _ = decode_mp3(mp3)
        sd.play(pcm, sample_rate)
        sd.wait()
        return pcm_to_wav_bytes(to_mono(pcm), sample_rate)
    except Exception as exc:
        logger.debug("TTS synthesis/playback failed (%s); falling back to spd-say", exc)
        _spd_say(text)
        return b""


def _spd_say(text: str) -> None:
    spd_bin = shutil.which("spd-say") or "/usr/bin/spd-say"
    try:
        subprocess.run([spd_bin, "-w", text], check=False)  # nosec B603
    except FileNotFoundError:
        logger.warning("spd-say not found on system; speech synthesis skipped")