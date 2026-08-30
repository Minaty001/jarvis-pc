"""
Microphone Input — Auto-detect and capture audio from default mic.
Uses sounddevice for cross-platform audio capture.
Auto-requests mic permission on Linux via PulseAudio/PipeWire.
"""

import os
import subprocess
import threading
import queue
from typing import Optional

import numpy as np

from config.logger import get_logger
from config.settings import settings

logger = get_logger("voice.mic")

try:
    import sounddevice as sd
    HAS_AUDIO = True
except Exception:
    HAS_AUDIO = False
    logger.warning("sounddevice not available. Mic capture disabled.")


def _ensure_pulseaudio_permission() -> bool:
    """Auto-grant mic permission by ensuring PulseAudio/PipeWire is accessible."""
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
            logger.info("PulseAudio started for mic access")
        return True
    except FileNotFoundError:
        logger.info("PulseAudio not found, trying PipeWire...")
    except Exception as e:
        logger.warning("PulseAudio check failed: %s", e)

    try:
        result = subprocess.run(
            ["pipewire", "--version"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            logger.info("PipeWire available for audio")
            return True
    except (FileNotFoundError, Exception):
        pass

    return HAS_AUDIO


class Microphone:
    """Auto-detecting microphone capture with ring buffer."""

    def __init__(self, sample_rate: int = None, channels: int = 1):
        self.sample_rate = sample_rate or settings.sample_rate
        self.channels = channels
        self._stream = None
        self._buffer: queue.Queue = queue.Queue(maxsize=50)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._permission_granted = False

    def _request_permission(self) -> bool:
        """Auto-request microphone permission."""
        if self._permission_granted:
            return True
        if not HAS_AUDIO:
            return False

        _ensure_pulseaudio_permission()

        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="float32"):
                pass
            self._permission_granted = True
            logger.info("Mic permission granted (auto)")
            return True
        except Exception as e:
            logger.error("Mic permission denied: %s", e)
            return False

    def list_devices(self) -> list[dict]:
        """List available audio input devices."""
        if not HAS_AUDIO:
            return []
        devices = sd.query_devices()
        inputs = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                inputs.append({"index": i, "name": d["name"], "channels": d["max_input_channels"]})
        return inputs

    def get_default_device(self) -> Optional[int]:
        """Get default input device index."""
        if not HAS_AUDIO:
            return None
        try:
            return sd.default.device[0]
        except Exception:
            return None

    def start(self) -> None:
        """Start capturing audio in background thread."""
        if not HAS_AUDIO:
            logger.error("Cannot start mic: sounddevice not available")
            return

        if not self._request_permission():
            logger.error("Cannot start mic: permission not granted")
            return

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Microphone capture started (rate=%d)", self.sample_rate)

    def _capture_loop(self) -> None:
        """Continuous audio capture loop."""
        blocksize = int(self.sample_rate * 0.03)  # 30ms chunks

        def callback(indata, frames, time_info, status):
            if status:
                logger.warning("Mic status: %s", status)
            audio = np.copy(indata[:, 0] if indata.ndim > 1 else indata)
            try:
                self._buffer.put_nowait(audio)
            except queue.Full:
                try:
                    self._buffer.get_nowait()
                    self._buffer.put_nowait(audio)
                except queue.Full:
                    pass

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=blocksize,
                dtype="float32",
                callback=callback,
            ):
                while self._running:
                    sd.sleep(100)
        except Exception as e:
            logger.error("Mic capture error: %s", e)

    def read(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """Read next audio chunk from buffer."""
        try:
            return self._buffer.get(timeout=timeout)
        except queue.Empty:
            return None

    def read_blocking(self, duration_sec: float) -> Optional[np.ndarray]:
        """Read audio for a fixed duration."""
        chunks = []
        samples_needed = int(self.sample_rate * duration_sec)
        collected = 0

        while collected < samples_needed:
            chunk = self.read(timeout=0.5)
            if chunk is None:
                break
            chunks.append(chunk)
            collected += len(chunk)

        if not chunks:
            return None
        return np.concatenate(chunks)

    def stop(self) -> None:
        """Stop capturing audio."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Microphone capture stopped")


microphone = Microphone()
