import logging
import os
import threading
import time
import warnings
from typing import Callable, List, Optional

# Suppress onnxruntime provider warnings
warnings.filterwarnings("ignore", category=UserWarning, module="onnxruntime")
os.environ["ORT_LOGGING_LEVEL"] = "3"

import numpy as np
import openwakeword
from openwakeword.model import Model
import sounddevice as sd

from .audio_device import detect_and_configure_bluetooth_mic, get_active_microphone_name
from .voice import init_voice, speak_yes_boss_async

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [WakeWord] %(message)s",
)
logger = logging.getLogger("jarvis.wake_word")


class WakeWordDetector:
    """Continuously listens for wake words in background, responds, and restarts cleanly."""

    def __init__(
        self,
        wake_words: Optional[List[str]] = None,
        threshold: float = 0.35,
        debounce_seconds: float = 1.5,
        sample_rate: int = 16000,
        chunk_size: int = 1280,
        device: Optional[int | str] = None,
        on_wake_word: Optional[Callable[[str, float], None]] = None,
        auto_start: bool = False,
    ) -> None:
        """Initialize WakeWordDetector."""
        self.wake_words = wake_words or ["hey_jarvis"]
        self.threshold = threshold
        self.debounce_seconds = debounce_seconds
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.device = device
        self.on_wake_word = on_wake_word

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_trigger_time: float = 0.0

        # Load openWakeWord models
        self.model = self._load_models()

        if auto_start:
            self.start()

    def _load_models(self) -> Model:
        """Find and load specified openWakeWord models."""
        all_paths = openwakeword.get_pretrained_model_paths()
        selected_paths: List[str] = []

        for target in self.wake_words:
            matched = False
            for path in all_paths:
                if target.lower() in path.lower():
                    selected_paths.append(path)
                    matched = True
                    break
            if not matched:
                logger.warning("No exact model path match for '%s', searching default pool...", target)

        if selected_paths:
            logger.info("Loading wake word models: %s", selected_paths)
            return Model(wakeword_model_paths=selected_paths)
        
        logger.info("Loading all default openWakeWord models")
        return Model()

    def reset(self) -> None:
        """Reset internal model buffers and state for a fresh restart."""
        try:
            self.model.reset()
            self._last_trigger_time = time.time()
            logger.info("🔄 Wake word detector state reset and restarted for next wake word.")
        except Exception as err:
            logger.error("Error resetting wake word model: %s", err)

    def _audio_callback(self, in_data, frames, time_info, status) -> None:
        """Process incoming audio chunk from sounddevice stream."""
        if status:
            logger.debug("Audio stream status: %s", status)

        if not self._running:
            return

        # Convert raw buffer to pristine int16 numpy array
        audio_chunk = np.frombuffer(in_data, dtype=np.int16)
        
        # Periodic audio energy check for live monitoring
        now = time.time()
        if hasattr(self, "_last_energy_log") and (now - self._last_energy_log) >= 5.0:
            self._last_energy_log = now
            rms = np.sqrt(np.mean(audio_chunk.astype(float) ** 2)) if len(audio_chunk) > 0 else 0
            logger.info("🎤 Listening active | Mic RMS: %.1f | Target: 'hey_jarvis' (Threshold: %.2f)", rms, self.threshold)
        elif not hasattr(self, "_last_energy_log"):
            self._last_energy_log = now

        try:
            # Predict scores for audio frame
            predictions = self.model.predict(audio_chunk)

            for raw_name, score in predictions.items():
                is_target = any(target.lower() in raw_name.lower() for target in self.wake_words) or "jarvis" in raw_name.lower()
                if is_target and score >= self.threshold:
                    if (now - self._last_trigger_time) >= self.debounce_seconds:
                        self._last_trigger_time = now
                        self._handle_detection("hey_jarvis", float(score))
        except Exception as err:
            logger.error("Error during inference: %s", err)

    def _handle_detection(self, name: str, score: float) -> None:
        """Handle detected wake word event and restart detector state."""
        logger.info(">>> WAKE WORD DETECTED: '%s' (Confidence: %.2f) <<<", name, score)
        if self.on_wake_word:
            try:
                self.on_wake_word(name, score)
            except Exception as err:
                logger.error("Error in on_wake_word callback: %s", err)
        
        # Restart internal buffers cleanly
        self.reset()

    def _listen_loop(self) -> None:
        """Audio streaming loop run inside a background thread."""
        logger.info("Wake word background listener active (Sample Rate: %d, Chunk: %d)...", self.sample_rate, self.chunk_size)
        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                channels=1,
                dtype="int16",
                device=self.device,
                callback=self._audio_callback,
            ):
                while self._running:
                    time.sleep(0.05)
        except Exception as err:
            logger.error("Audio stream failed: %s", err)
            self._running = False

    def start(self) -> None:
        """Start listening in the background."""
        if self._running:
            logger.warning("WakeWordDetector is already running.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="WakeWordListener")
        self._thread.start()
        logger.info("WakeWordDetector started in background thread.")

    def stop(self) -> None:
        """Stop listening and terminate background thread."""
        if not self._running:
            return

        logger.info("Stopping WakeWordDetector...")
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("WakeWordDetector stopped.")

    @property
    def is_running(self) -> bool:
        """Check if detector is currently running."""
        return self._running
