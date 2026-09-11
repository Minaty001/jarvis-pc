"""Text-to-speech via edge-tts neural voices, with spd-say fallback if offline."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import shutil
import subprocess  # nosec B404

try:
    import edge_tts
except ImportError:
    edge_tts = None  # type: ignore

from jarvis.voice.audio import decode_mp3, pcm_to_wav_bytes, to_mono

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "en-US-GuyNeural"


async def synthesize_async(text: str, voice: str = DEFAULT_VOICE, timeout: float = 30.0) -> bytes:
    """Synthesize speech to MP3 bytes via edge-tts asynchronously."""
    if edge_tts is None:
        raise RuntimeError("edge-tts library is not installed or available.")

    communicate = edge_tts.Communicate(text, voice)
    data = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            data.extend(chunk["data"])
    return bytes(data)


def synthesize(text: str, voice: str = DEFAULT_VOICE, timeout: float = 30.0) -> bytes:
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
                asyncio.run, asyncio.wait_for(synthesize_async(text, voice, timeout), timeout)
            ).result()
    else:
        return asyncio.run(asyncio.wait_for(synthesize_async(text, voice, timeout), timeout))


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