"""Microphone capture via sounddevice — 16 kHz mono int16 stream + record-to-silence."""

import logging
import queue
from collections import deque
from typing import Callable, Optional

import numpy as np

from jarvis.voice.vad import DEFAULT_SPEECH_THRESHOLD, is_speech

logger = logging.getLogger(__name__)

RATE = 16000
CHUNK = 1280  # 80 ms @ 16 kHz — matches Vosk frame size
MAX_SECONDS = 12.0
SILENCE_MS = 900


class Microphone:
    def __init__(self):
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue()

    def _callback(self, indata, frames, time_info, status):
        if isinstance(indata, np.ndarray):
            self._queue.put(indata.copy())
        else:
            self._queue.put(np.frombuffer(indata, dtype=np.int16).copy())

    def iter_chunks(self, level_callback: Optional[Callable[[float], None]] = None):
        """Yield int16 mono (chunk,) arrays until the stream is closed."""
        import sounddevice as sd

        stream = sd.InputStream(
            samplerate=RATE, channels=1, dtype="int16", blocksize=CHUNK, callback=self._callback
        )
        stream.start()
        try:
            while True:
                chunk = self._queue.get().ravel()
                if level_callback and len(chunk) > 0:
                    try:
                        rms = float(np.sqrt(np.mean(chunk.astype(float) ** 2))) / 32768.0
                        level_callback(min(1.0, rms * 4.5))
                    except Exception as exc:
                        logger.debug("Failed to compute or dispatch microphone audio level: %s", exc)
                yield chunk
        finally:
            stream.stop()
            stream.close()

    def record_until_silence(self, level_callback: Optional[Callable[[float], None]] = None) -> np.ndarray:
        """Record until `SILENCE_MS` of quiet, capped at `MAX_SECONDS`.

        A short pre-roll window is kept so the start of a phrase is captured.
        Returns int16 mono PCM (possibly empty if nothing was heard).
        """
        chunk_ms = 1000 * CHUNK // RATE
        pre_roll = deque(maxlen=max(1, 400 // chunk_ms))
        frames: list[np.ndarray] = []
        silent_ms = 0
        unspoken_ms = 0
        spoke = False

        for chunk in self.iter_chunks(level_callback=level_callback):
            pre_roll.append(chunk)
            if is_speech(chunk):
                spoke = True
                if not frames:
                    frames.extend(pre_roll)
                frames.append(chunk)
                silent_ms = 0
            elif spoke:
                silent_ms += chunk_ms
                frames.append(chunk)
            else:
                unspoken_ms += chunk_ms

            if spoke and (silent_ms >= SILENCE_MS or len(frames) * chunk_ms / 1000 >= MAX_SECONDS):
                break
            if not spoke and unspoken_ms >= 4000:
                break

        if not spoke:
            return np.array([], dtype="<i2")
        return np.concatenate(frames) if frames else np.array([], dtype="<i2")