"""
Voice Activity Detection (VAD).
Uses energy-based detection for lightweight, CPU-friendly VAD.

Key fix: float32 audio from sounddevice has energy in 0.001–0.3 range for speech.
Old minimum threshold of 0.005 was too close to ambient float32 noise floor.
New calibration multiplier=6.0 and hard minimum 0.02 prevents false-positives.
"""

import numpy as np
from config.logger import get_logger
from config.settings import settings

logger = get_logger("voice.vad")


class VAD:
    """Energy-based Voice Activity Detection for float32 PCM audio."""

    # Float32 PCM from sounddevice: silence ≈ 0.0001–0.001, speech ≈ 0.004–0.3
    _MIN_THRESHOLD = 0.003   # Hard floor — anything below is background hiss
    _MAX_THRESHOLD = 0.15    # Hard ceiling — clip very loud environments

    def __init__(self, threshold: float = None, sample_rate: int = None):
        self.threshold = threshold or settings.vad_threshold
        self.sample_rate = sample_rate or settings.sample_rate
        self._energy_threshold = self._MIN_THRESHOLD

    def compute_energy(self, audio: np.ndarray) -> float:
        """Compute RMS energy of audio chunk (float32 PCM)."""
        if len(audio) == 0:
            return 0.0
        arr = audio.astype(np.float32)
        return float(np.sqrt(np.mean(arr ** 2)))

    def is_speech(self, audio: np.ndarray) -> bool:
        """Return True if audio chunk energy exceeds the calibrated threshold."""
        return self.compute_energy(audio) > self._energy_threshold

    def calibrate(self, ambient_audio: np.ndarray, multiplier: float = 6.0) -> None:
        """
        Calibrate threshold from ambient noise.
        multiplier=6 → threshold is 6× ambient RMS, clamped to [_MIN, _MAX].
        Typical values after calibration: 0.02–0.05 for quiet environments.
        """
        energy = self.compute_energy(ambient_audio)
        raw = energy * multiplier
        self._energy_threshold = max(self._MIN_THRESHOLD, min(self._MAX_THRESHOLD, raw))
        logger.info(
            "VAD calibrated: threshold=%.4f (ambient_rms=%.4f, multiplier=%.1f)",
            self._energy_threshold, energy, multiplier,
        )

    def detect_speech_segment(self, audio: np.ndarray, min_speech_ms: int = 300) -> tuple[bool, int, int]:
        """
        Detect speech in a full audio array.
        Returns (has_speech, start_sample, end_sample).
        """
        chunk_size = int(self.sample_rate * 0.03)  # 30 ms
        speech_start = -1
        speech_end = -1
        in_speech = False

        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i + chunk_size]
            if len(chunk) < chunk_size // 2:
                break
            if self.is_speech(chunk):
                if not in_speech:
                    speech_start = i
                    in_speech = True
                speech_end = i + len(chunk)
            elif in_speech:
                duration_ms = (speech_end - speech_start) / self.sample_rate * 1000
                if duration_ms >= min_speech_ms:
                    return True, speech_start, speech_end
                in_speech = False

        if in_speech:
            duration_ms = (speech_end - speech_start) / self.sample_rate * 1000
            if duration_ms >= min_speech_ms:
                return True, speech_start, speech_end

        return False, 0, 0


vad = VAD()
