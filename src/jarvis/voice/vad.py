"""Voice activity detection — RMS energy gating over 16 kHz int16 mono frames."""

import numpy as np

DEFAULT_SPEECH_THRESHOLD = 300.0


def rms(pcm: np.ndarray) -> float:
    return float(np.sqrt(np.mean(pcm.astype("f4") ** 2))) if len(pcm) else 0.0


def is_speech(pcm: np.ndarray, threshold: float = DEFAULT_SPEECH_THRESHOLD) -> bool:
    return rms(pcm) >= threshold