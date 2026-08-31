"""
Text-to-Speech (TTS) — edge-tts streaming.
Microsoft Edge neural voices with async streaming.
Auto-requests speaker permission on Linux.
"""

import subprocess
import asyncio
import tempfile
from pathlib import Path
from typing import Optional

from config.logger import get_logger
from config.settings import settings

logger = get_logger("voice.tts")

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False
    logger.warning("edge-tts not installed. TTS disabled.")

try:
    import sounddevice as sd
    import soundfile as sf
    HAS_PLAYBACK = True
except (ImportError, OSError, Exception) as e:
    HAS_PLAYBACK = False
    logger.warning("sounddevice/soundfile audio playback unavailable: %s", e)


def _ensure_pulseaudio_output() -> bool:
    """Auto-grant speaker permission by ensuring PulseAudio output is accessible."""
    try:
        result = subprocess.run(
            ["pulseaudio", "--check"],
            capture_output=True, timeout=3,
        )
        if result.returncode != 0:
            subprocess.run(
                ["pulseaudio", "--start", "--exit-idle-time=-1"],
                capture_output=True, timeout=5,
            )
            logger.info("PulseAudio started for speaker access")
        return True
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning("PulseAudio check failed: %s", e)

    try:
        result = subprocess.run(
            ["pipewire", "--version"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            return True
    except (FileNotFoundError, Exception):
        pass

    return HAS_PLAYBACK


class EdgeTTS:
    """Microsoft Edge neural TTS with streaming output."""

    def __init__(self, voice: str = None, rate: str = None, volume: str = None):
        self.voice = voice or settings.jarvis_voice
        self.rate = rate or settings.jarvis_rate
        self.volume = volume or settings.jarvis_volume
        self._playing = False
        # Auto-request speaker permission on init
        if HAS_PLAYBACK:
            _ensure_pulseaudio_output()

    async def synthesize(self, text: str) -> Optional[bytes]:
        """Synthesize text to MP3 audio bytes."""
        if not HAS_EDGE_TTS:
            logger.error("edge-tts not available")
            return None

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
            )
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            return audio_data if audio_data else None
        except Exception as e:
            logger.error("TTS synthesis error: %s", e)
            return None

    async def speak(self, text: str) -> bool:
        """Synthesize and play text through speakers."""
        if not HAS_PLAYBACK:
            logger.error("sounddevice/soundfile not available for playback")
            return False

        # Auto-request speaker permission
        _ensure_pulseaudio_output()

        audio_bytes = await self.synthesize(text)
        if not audio_bytes:
            return False

        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as tmp:
                tmp.write(audio_data := audio_bytes)
                tmp.flush()
                data, samplerate = sf.read(tmp.name)
                self._playing = True
                sd.play(data, samplerate)
                sd.wait()
                self._playing = False
                return True
        except Exception as e:
            logger.error("TTS playback error: %s", e)
            self._playing = False
            return False

    async def speak_async(self, text: str) -> None:
        """Non-blocking speak — fire and forget."""
        asyncio.create_task(self.speak(text))

    def set_voice(self, voice: str) -> None:
        """Change the TTS voice."""
        self.voice = voice
        logger.info("TTS voice changed to: %s", voice)

    @property
    def is_playing(self) -> bool:
        return self._playing


edge_tts_engine = EdgeTTS()
