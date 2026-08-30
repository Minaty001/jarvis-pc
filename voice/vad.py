"""
Voice Activity Detection (VAD).
Uses energy-based detection for lightweight, CPU-friendly VAD.
"""

import numpy as np
from config.logger import get_logger
from config.settings import settings

logger = get_logger("voice.vad")


class VAD:
    """Energy-based Voice Activity Detection."""

    def __init__(self, threshold: float = None, sample_rate: int = None):
        self.threshold = threshold or settings.vad_threshold
        self.sample_rate = sample_rate or settings.sample_rate
        self._energy_threshold = 0.01  # Will be calibrated

    def compute_energy(self, audio: np.ndarray) -> float:
        """Compute RMS energy of audio chunk."""
        if len(audio) == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))

    def is_speech(self, audio: np.ndarray) -> bool:
        """Check if audio chunk contains speech."""
        energy = self.compute_energy(audio)
        return energy > self._energy_threshold

    def calibrate(self, ambient_audio: np.ndarray, multiplier: float = 3.0) -> None:
        """Calibrate threshold based on ambient noise."""
        energy = self.compute_energy(ambient_audio)
        self._energy_threshold = energy * multiplier
        logger.info("VAD calibrated: threshold=%.4f (ambient=%.4f)", self._energy_threshold, energy)

    def detect_speech_segment(self, audio: np.ndarray, min_speech_ms: int = 300) -> tuple[bool, int, int]:
        """
        Detect speech in audio array.
        Returns (has_speech, start_sample, end_sample).
        """
        chunk_size = int(self.sample_rate * 0.03)  # 30ms
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
