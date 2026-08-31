"""
Wake Word Detection — openWakeWord ONNX integration.
Uses official openWakeWord engine with custom hey_jarvis ONNX model.
"""

from pathlib import Path
from typing import Optional
import numpy as np

from config.logger import get_logger
from config.settings import settings

logger = get_logger("voice.wakeword")

try:
    from openwakeword.model import Model
    HAS_OPENWAKEWORD = True
except ImportError:
    HAS_OPENWAKEWORD = False
    logger.warning("openwakeword library not installed. Wake word disabled.")

try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False
    logger.warning("onnxruntime not installed. Wake word disabled.")


class WakeWordDetector:
    """openWakeWord ONNX wake word detector for 'Jarvis' / 'Hey Jarvis'."""

    def __init__(self, threshold: float = None):
        self.threshold = threshold or settings.wake_threshold
        self._model: Optional[Model] = None
        self._loaded = False
        self._consecutive_errors = 0
        self._error_log_interval = 50

    def load(self) -> bool:
        """Load openWakeWord ONNX model."""
        if not HAS_OPENWAKEWORD or not HAS_ONNX:
            return False

        wakeword_dir = settings.wakeword_dir
        hey_jarvis_model = wakeword_dir / "hey_jarvis.onnx"

        if not hey_jarvis_model.exists():
            logger.error("Wake word model not found: %s", hey_jarvis_model)
            return False

        try:
            self._model = Model(
                wakeword_model_paths=[str(hey_jarvis_model)],
            )
            self._loaded = True
            logger.info("openWakeWord ONNX model loaded from %s", hey_jarvis_model)
            return True
        except Exception as e:
            logger.error("Failed to load openWakeWord model: %s", e)
            return False

    def detect(self, audio: np.ndarray) -> tuple[bool, float]:
        """
        Run detection on 16kHz float32 or int16 PCM audio array.
        Returns (is_wake_word, confidence_score).
        """
        if not self._loaded or self._model is None:
            return False, 0.0

        # RMS Pre-filter to skip silent buffers
        audio_float = audio.astype(np.float32)
        if audio_float.max() > 1.0:
            audio_float = audio_float / 32768.0

        rms = float(np.sqrt(np.mean(audio_float ** 2)))
        if rms < 0.002:
            return False, 0.0

        try:
            # openWakeWord expects int16 PCM [-32768, 32767]
            pcm_int16 = (audio_float * 32768.0).astype(np.int16)
            prediction = self._model.predict(pcm_int16)

            score = 0.0
            for model_name, predictions in prediction.items():
                score = float(predictions)
                break

            is_wake = score >= self.threshold
            self._consecutive_errors = 0
            return is_wake, score
        except Exception as e:
            self._consecutive_errors += 1
            if self._consecutive_errors % self._error_log_interval == 1:
                logger.warning("Wake word detection error (consecutive %d): %s",
                               self._consecutive_errors, e)
            return False, 0.0

    @property
    def is_loaded(self) -> bool:
        return self._loaded


wake_word_detector = WakeWordDetector()
