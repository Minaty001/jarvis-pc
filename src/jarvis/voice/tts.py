"""Text-to-speech via edge-tts neural voices, with spd-say fallback if offline."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import shutil
import subprocess  # nosec B404
import threading
from typing import Any, Callable, Optional

try:
    import edge_tts
except ImportError:
    edge_tts = None  # type: ignore

from jarvis.voice.audio import decode_mp3, pcm_to_wav_bytes, to_mono
from jarvis.voice.profiles import get_profile_manager

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "en-GB-RyanNeural"


async def synthesize_async(
    text: str,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
    volume: Optional[str] = None,
    timeout: float = 30.0,
) -> bytes:
    """Synthesize speech to MP3 bytes via edge-tts asynchronously with acoustic modulation."""
    if edge_tts is None:
        raise RuntimeError("edge-tts library is not installed or available.")

    if not text or not text.strip():
        return b""

    profile = get_profile_manager().get_active_profile()
    target_voice = voice or profile.voice_id
    target_rate = rate or profile.rate
    target_pitch = pitch or profile.pitch
    target_volume = volume or profile.volume

    communicate = edge_tts.Communicate(
        text=text,
        voice=target_voice,
        rate=target_rate,
        pitch=target_pitch,
        volume=target_volume,
    )
    data = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            data.extend(chunk["data"])
    return bytes(data)


def synthesize(
    text: str,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
    volume: Optional[str] = None,
    timeout: float = 30.0,
) -> bytes:
    """Synthesize speech to MP3 bytes via edge-tts (safe from sync and running event loops)."""
    if edge_tts is None:
        raise RuntimeError("edge-tts library is not installed or available.")

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                asyncio.run,
                asyncio.wait_for(
                    synthesize_async(text, voice=voice, rate=rate, pitch=pitch, volume=volume, timeout=timeout),
                    timeout,
                ),
            ).result()
    else:
        return asyncio.run(
            asyncio.wait_for(
                synthesize_async(text, voice=voice, rate=rate, pitch=pitch, volume=volume, timeout=timeout),
                timeout,
            )
        )


def speak(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Speak `text` through the default audio output.

    Returns decoded WAV bytes. Falls back to spd-say / espeak when edge-tts is
    unavailable or offline.
    """
    if not text or not text.strip():
        return b""
    try:
        mp3 = synthesize(text, voice)
        import sounddevice as sd

        pcm, sample_rate, _ = decode_mp3(mp3)
        sd.play(pcm, sample_rate)
        sd.wait()
        return pcm_to_wav_bytes(to_mono(pcm), sample_rate)
    except Exception as exc:
        logger.debug("TTS synthesis/playback failed (%s); falling back to offline speech synthesizers", exc)
        _offline_say(text)
        return b""


def speak_interruptible(
    text: str,
    voice: str = DEFAULT_VOICE,
    interrupt_event: Optional[threading.Event] = None,
    level_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """Speak `text` with chunked streaming and support for instantaneous interruption."""
    if not text or not text.strip():
        return True
    try:
        from jarvis.voice.duplex import InterruptibleSpeaker

        mp3 = synthesize(text, voice)
        pcm, sample_rate, _ = decode_mp3(mp3)
        speaker = InterruptibleSpeaker()
        return speaker.play(
            pcm,
            sample_rate=sample_rate,
            interrupt_event=interrupt_event,
            level_callback=level_callback,
        )
    except Exception as exc:
        logger.debug("Interruptible TTS failed (%s); falling back to standard offline speech", exc)
        _offline_say(text)
        return True


async def speak_async(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Asynchronous non-blocking speech playback helper."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, speak, text, voice)


def _offline_say(text: str) -> None:
    # 1. Try spd-say (standard on Ubuntu / Linux Mint)
    spd_bin = shutil.which("spd-say") or "/usr/bin/spd-say"
    if os.path.exists(spd_bin):
        try:
            subprocess.run([spd_bin, "-w", text], check=False)  # nosec B603
            return
        except Exception as exc:
            logger.debug("spd-say invocation failed: %s", exc)

    # 2. Try espeak-ng / espeak
    espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak")
    if espeak_bin:
        try:
            subprocess.run([espeak_bin, text], check=False)  # nosec B603
            return
        except Exception as exc:
            logger.debug("espeak invocation failed: %s", exc)

    logger.warning("No offline speech synthesizer available; audio output skipped.")