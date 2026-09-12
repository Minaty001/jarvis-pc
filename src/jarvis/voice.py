"""Voice Output and Speech Synthesis for JARVIS.

Provides zero-latency pre-cached speech playback and real-time dynamic TTS output.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import shutil
import subprocess
import threading
from typing import Optional

import miniaudio
import numpy as np
import sounddevice as sd

logger = logging.getLogger("jarvis.voice")

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
CACHE_FILE = ASSETS_DIR / "yes_boss.npy"
_cached_yes_boss: Optional[np.ndarray] = None


def init_voice() -> None:
    """Pre-load or generate instant 'Yes boss' voice cache."""
    global _cached_yes_boss
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists():
        try:
            _cached_yes_boss = np.load(CACHE_FILE)
            logger.debug("Loaded cached 'Yes boss' audio (%d samples)", len(_cached_yes_boss))
            return
        except Exception as err:
            logger.warning("Failed to load cached audio: %s", err)

    # Generate if not existing
    try:
        import edge_tts

        async def _generate():
            comm = edge_tts.Communicate("Yes boss", "en-US-ChristopherNeural")
            audio = b""
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    audio += chunk["data"]
            decoded = miniaudio.decode(audio, nchannels=1, sample_rate=16000)
            samples = np.frombuffer(decoded.samples, dtype=np.int16)
            np.save(CACHE_FILE, samples)
            return samples

        _cached_yes_boss = asyncio.run(_generate())
        logger.info("Generated and cached high quality 'Yes boss' audio.")
    except Exception as err:
        logger.warning("Could not pre-render voice cache: %s", err)


def speak_yes_boss(block: bool = True) -> None:
    """Play 'Yes boss' audio either synchronously (blocking) or asynchronously."""
    def _play():
        global _cached_yes_boss
        if _cached_yes_boss is None:
            init_voice()

        if _cached_yes_boss is not None:
            try:
                sd.play(_cached_yes_boss, samplerate=16000)
                sd.wait()
                return
            except Exception as err:
                logger.error("Error during sounddevice playback: %s", err)

        # Fallback to system synthesizer
        if shutil.which("spd-say"):
            subprocess.run(["spd-say", "-t", "female3", "Yes boss"], check=False)
        elif shutil.which("espeak"):
            subprocess.run(["espeak", "Yes boss"], check=False)

    if block:
        _play()
    else:
        threading.Thread(target=_play, daemon=True, name="VoiceOutputThread").start()


def speak_yes_boss_async() -> None:
    """Play 'Yes boss' immediately in a background thread without blocking."""
    speak_yes_boss(block=False)


def speak_text(text: str, block: bool = False) -> None:
    """Synthesize and speak arbitrary text aloud."""
    clean_text = text.strip()
    if not clean_text:
        return

    def _speak_worker():
        try:
            import edge_tts

            async def _synth():
                comm = edge_tts.Communicate(clean_text, "en-US-ChristopherNeural")
                audio = b""
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        audio += chunk["data"]
                decoded = miniaudio.decode(audio, nchannels=1, sample_rate=16000)
                return np.frombuffer(decoded.samples, dtype=np.int16)

            samples = asyncio.run(_synth())
            sd.play(samples, samplerate=16000)
            sd.wait()
            return
        except Exception as err:
            logger.debug("Edge TTS failed, using system fallback: %s", err)

        # Fallback to system synthesizer
        if shutil.which("spd-say"):
            subprocess.run(["spd-say", "-t", "female3", clean_text], check=False)
        elif shutil.which("espeak"):
            subprocess.run(["espeak", clean_text], check=False)

    if block:
        _speak_worker()
    else:
        threading.Thread(target=_speak_worker, daemon=True, name="VoiceSynthThread").start()
