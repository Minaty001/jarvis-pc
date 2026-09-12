"""Voice Output and Speech Synthesis for JARVIS.

Provides zero-latency pre-cached speech playback and real-time TTS output.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import threading
from typing import Optional

import miniaudio
import numpy as np
import sounddevice as sd

logger = logging.getLogger("jarvis.voice")

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
CACHE_FILE = ASSETS_DIR / "yes_boss.npy"
_cached_pcm: Optional[np.ndarray] = None


def init_voice() -> None:
    """Pre-load or generate instant 'Yes boss' voice cache."""
    global _cached_pcm
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists():
        try:
            _cached_pcm = np.load(CACHE_FILE)
            logger.debug("Loaded cached 'Yes boss' audio (%d samples)", len(_cached_pcm))
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

        _cached_pcm = asyncio.run(_generate())
        logger.info("Generated and cached high quality 'Yes boss' audio.")
    except Exception as err:
        logger.warning("Could not pre-render voice cache: %s", err)


def speak_yes_boss_async() -> None:
    """Play 'Yes boss' immediately in a background thread without blocking."""
    def _play():
        global _cached_pcm
        if _cached_pcm is None:
            init_voice()

        if _cached_pcm is not None:
            try:
                sd.play(_cached_pcm, samplerate=16000)
                sd.wait()
                return
            except Exception as err:
                logger.error("Error during sounddevice playback: %s", err)

        # Fallback to system synthesizer
        import shutil
        import subprocess
        if shutil.which("spd-say"):
            subprocess.run(["spd-say", "-t", "female3", "Yes boss"], check=False)
        elif shutil.which("espeak"):
            subprocess.run(["espeak", "Yes boss"], check=False)

    threading.Thread(target=_play, daemon=True, name="VoiceOutputThread").start()
