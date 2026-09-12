"""Speech-to-Text Streaming Command Transcriber for JARVIS.

Accepts audio chunks directly from the main continuous audio stream,
provides real-time partial transcription, detects end-of-speech silence,
and outputs finalized command text.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional, Tuple

import numpy as np
import vosk

# Suppress noisy vosk logs
vosk.SetLogLevel(-1)

logger = logging.getLogger("jarvis.stt")

_vosk_model: Optional[vosk.Model] = None


def get_stt_model() -> Optional[vosk.Model]:
    """Load or retrieve singleton Vosk STT Model."""
    global _vosk_model
    if _vosk_model is None:
        try:
            logger.info("Loading Vosk speech-to-text model (vosk-model-small-en-us-0.15)...")
            _vosk_model = vosk.Model(model_name="vosk-model-small-en-us-0.15")
        except Exception as err:
            logger.warning("Could not load Vosk model: %s", err)
    return _vosk_model


class StreamTranscriber:
    """Streaming command transcriber operating on a shared audio stream."""

    def __init__(
        self,
        sample_rate: int = 16000,
        silence_timeout: float = 1.0,
        max_duration: float = 9.0,
        energy_threshold: float = 450.0,
        no_speech_timeout: float = 4.5,
    ) -> None:
        self.sample_rate = sample_rate
        self.silence_timeout = silence_timeout
        self.max_duration = max_duration
        self.energy_threshold = energy_threshold
        self.no_speech_timeout = no_speech_timeout

        self.model = get_stt_model()
        self.rec: Optional[vosk.KaldiRecognizer] = None
        self._start_time: float = 0.0
        self._last_speech_time: float = 0.0
        self._speech_started: bool = False
        self._accumulated_text: str = ""
        self._last_final_boundary_time: float = 0.0

    def start(self) -> None:
        """Start a new command transcription session."""
        if self.model is not None:
            self.rec = vosk.KaldiRecognizer(self.model, self.sample_rate)
            self.rec.SetWords(False)
        self._start_time = time.time()
        self._last_speech_time = self._start_time
        self._speech_started = False
        self._accumulated_text = ""
        self._last_final_boundary_time = 0.0

    def process_chunk(self, audio_chunk: np.ndarray | bytes) -> Tuple[bool, str, str]:
        """Feed an audio chunk into transcriber.

        Returns:
            Tuple of (is_complete: bool, partial_text: str, current_full_text: str)
        """
        if self.rec is None:
            return True, "", self._accumulated_text.strip()

        if isinstance(audio_chunk, bytes):
            raw_bytes = audio_chunk
            audio_array = np.frombuffer(raw_bytes, dtype=np.int16)
        else:
            audio_array = audio_chunk
            raw_bytes = audio_chunk.tobytes()

        now = time.time()
        elapsed = now - self._start_time

        # Calculate chunk RMS
        rms = np.sqrt(np.mean(audio_array.astype(float) ** 2)) if len(audio_array) > 0 else 0
        if rms >= self.energy_threshold:
            self._speech_started = True
            self._last_speech_time = now

        # Feed to Kaldi Recognizer
        is_chunk_final = self.rec.AcceptWaveform(raw_bytes)
        latest_partial = ""

        if is_chunk_final:
            res = json.loads(self.rec.Result())
            text = res.get("text", "")
            if text:
                self._accumulated_text = f"{self._accumulated_text} {text}".strip()
                self._speech_started = True
                self._last_speech_time = now
                self._last_final_boundary_time = now
        else:
            partial_res = json.loads(self.rec.PartialResult())
            latest_partial = partial_res.get("partial", "")
            if latest_partial:
                self._speech_started = True
                self._last_speech_time = now

        current_full = f"{self._accumulated_text} {latest_partial}".strip()

        # Check termination conditions:
        # 1. Total max duration reached
        if elapsed >= self.max_duration:
            final_text = self.finalize()
            return True, latest_partial, final_text

        # 2. Vosk detected an utterance boundary and user paused for 0.6s
        if self._last_final_boundary_time > 0 and (now - self._last_final_boundary_time) >= 0.6 and not latest_partial:
            final_text = self.finalize()
            return True, "", final_text

        # 3. User spoke and has now stopped for silence_timeout (1.0s)
        if self._speech_started and (now - self._last_speech_time) >= self.silence_timeout:
            final_text = self.finalize()
            return True, latest_partial, final_text

        # 4. No speech started within no_speech_timeout (4.5s)
        if not self._speech_started and elapsed >= self.no_speech_timeout:
            self.finalize()
            return True, "", ""

        return False, latest_partial, current_full

    def finalize(self) -> str:
        """Finalize remaining recognizer buffers and return full transcription."""
        if self.rec is not None:
            try:
                final_res = json.loads(self.rec.FinalResult())
                final_text = final_res.get("text", "")
                if final_text:
                    self._accumulated_text = f"{self._accumulated_text} {final_text}".strip()
            except Exception as err:
                logger.debug("Error finalizing recognizer: %s", err)
            self.rec = None

        return self._accumulated_text.strip()
