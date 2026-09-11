"""Voice activity detection — RMS energy gating over 16 kHz int16 mono frames."""

import numpy as np

DEFAULT_SPEECH_THRESHOLD = 200.0


def rms(pcm: np.ndarray) -> float:
    if len(pcm) == 0:
        return 0.0
    pcm_f = pcm.astype("f4")
    # Remove DC bias for accurate acoustic energy measurement
    pcm_f = pcm_f - np.mean(pcm_f)
    return float(np.sqrt(np.mean(pcm_f**2)))


def is_speech(pcm: np.ndarray, threshold: float = DEFAULT_SPEECH_THRESHOLD) -> bool:
    return rms(pcm) >= threshold