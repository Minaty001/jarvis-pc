"""Full-duplex conversational audio with real-time barge-in interruption."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from typing import Callable, Optional

import numpy as np

from jarvis.config.settings import get_settings
from jarvis.voice import stt, vad
from jarvis.voice.audio import decode_mp3
from jarvis.voice.microphone import CHUNK, RATE, Microphone
from jarvis.voice.tts import synthesize
from jarvis.voice.wake_word import WakeWordDetector

logger = logging.getLogger(__name__)

BARGE_IN_WAKE_WORDS = ["jarvis", "hey jarvis", "stop", "hold on", "quiet", "cancel", "wait"]


class InterruptibleSpeaker:
    """Non-blocking chunked audio player with instantaneous (<20ms) interruption support."""

    def __init__(self):
        self._interrupt_event = threading.Event()
        self._is_playing = False
        self._lock = threading.Lock()

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    def interrupt(self) -> None:
        """Signal the current playback to abort immediately."""
        self._interrupt_event.set()

    def reset_interrupt(self) -> None:
        """Reset the interruption signal."""
        self._interrupt_event.clear()

    def play(
        self,
        pcm: np.ndarray,
        sample_rate: int = 24000,
        interrupt_event: Optional[threading.Event] = None,
        level_callback: Optional[Callable[[float], None]] = None,
    ) -> bool:
        """Play PCM audio data in small chunks.

        Returns True if played to completion, or False if interrupted.
        """
        import sounddevice as sd

        if interrupt_event is None:
            interrupt_event = self._interrupt_event

        self.reset_interrupt()
        with self._lock:
            self._is_playing = True

        blocksize = 1024
        total_frames = len(pcm)
        current_idx = 0

        try:
            if pcm.ndim == 1:
                channels = 1
            else:
                channels = pcm.shape[1]

            with sd.OutputStream(
                samplerate=sample_rate,
                channels=channels,
                dtype=pcm.dtype,
                blocksize=blocksize,
            ) as stream:
                while current_idx < total_frames:
                    if interrupt_event.is_set():
                        logger.debug("Playback interrupted by user barge-in.")
                        stream.abort()
                        return False

                    end_idx = min(current_idx + blocksize, total_frames)
                    chunk = pcm[current_idx:end_idx]

                    if level_callback and len(chunk) > 0:
                        try:
                            rms = float(np.sqrt(np.mean(chunk.astype(float) ** 2))) / 32768.0
                            level_callback(min(1.0, rms * 4.5))
                        except Exception as exc:
                            logger.debug("Waveform dispatch error during playback: %s", exc)

                    stream.write(chunk)
                    current_idx = end_idx

            return True
        except Exception as exc:
            logger.warning("Error during interruptible playback: %s", exc)
            return False
        finally:
            with self._lock:
                self._is_playing = False


class BargeInDetector:
    """Evaluates incoming microphone chunks during active speech for user interruption."""

    def __init__(
        self,
        mode: str = "vad_and_wake",
        sensitivity: float = 1.6,
        wake_phrases: Optional[list[str]] = None,
    ):
        self.mode = mode
        self.sensitivity = sensitivity
        try:
            self.detector: Optional[WakeWordDetector] = WakeWordDetector(wake_phrases or BARGE_IN_WAKE_WORDS)
        except Exception:
            self.detector = None

    def is_barge_in(self, mic_chunk: np.ndarray, is_speaking: bool = True) -> bool:
        """Determine whether the audio chunk indicates a user interruption."""
        if not is_speaking:
            return False

        # 1. Wake word / Stop word detection
        if self.mode in ("wake_only", "vad_and_wake") and self.detector is not None:
            try:
                if self.detector.feed(mic_chunk.tobytes()):
                    logger.info("Barge-in triggered via wake/stop phrase.")
                    return True
            except Exception as exc:
                logger.debug("Wake detector error in barge-in: %s", exc)

        # 2. Elevated energy threshold (to prevent acoustic echo false positives)
        if self.mode in ("vad_only", "vad_and_wake"):
            elevated_threshold = vad.DEFAULT_SPEECH_THRESHOLD * self.sensitivity
            if vad.is_speech(mic_chunk, threshold=elevated_threshold):
                logger.info("Barge-in triggered via voice energy threshold.")
                return True

        return False


class DuplexVoiceSession:
    """Full-duplex orchestrator enabling concurrent capture, playback, and barge-in."""

    def __init__(
        self,
        on_orb_state: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_chat: Optional[Callable[[str, str], None]] = None,
        on_level: Optional[Callable[[float], None]] = None,
    ):
        self.settings = get_settings()
        self.speaker = InterruptibleSpeaker()
        self.mic = Microphone()
        self.barge_detector = BargeInDetector(
            mode=self.settings.voice_barge_in_mode,
            sensitivity=self.settings.voice_barge_in_sensitivity,
        )

        self.on_orb_state = on_orb_state
        self.on_status = on_status
        self.on_chat = on_chat
        self.on_level = on_level

        self._active = False
        self._interrupt_event = threading.Event()

    def speak_and_listen_duplex(self, text: str, voice: Optional[str] = None) -> Optional[np.ndarray]:
        """Speak `text` while continuously monitoring the microphone for barge-in.

        If user interrupts, returns the captured PCM starting from the interruption.
        If speech finishes without interruption, returns None.
        """
        if not text or not text.strip():
            return None

        voice = voice or self.settings.voice
        try:
            mp3_bytes = synthesize(text, voice)
            pcm, sample_rate, _ = decode_mp3(mp3_bytes)
        except Exception as exc:
            logger.warning("TTS synthesis failed for duplex speech: %s", exc)
            return None

        self._interrupt_event.clear()
        playback_done = threading.Event()
        interrupted_by_user = threading.Event()

        def _play_worker():
            try:
                completed = self.speaker.play(
                    pcm,
                    sample_rate=sample_rate,
                    interrupt_event=self._interrupt_event,
                    level_callback=self.on_level,
                )
                if not completed:
                    interrupted_by_user.set()
            finally:
                playback_done.set()

        play_thread = threading.Thread(target=_play_worker, daemon=True, name="duplex-play-worker")
        play_thread.start()

        if self.on_orb_state:
            self.on_orb_state("speaking")
        if self.on_status:
            self.on_status("Speaking (Listening for interruption)...")

        # Full-duplex: stream mic chunks while playback is active
        chunk_ms = 1000 * CHUNK // RATE
        pre_roll = deque(maxlen=max(1, 400 // chunk_ms))
        captured_frames: list[np.ndarray] = []
        interrupted = False

        try:
            for chunk in self.mic.iter_chunks(level_callback=self.on_level):
                if playback_done.is_set():
                    break

                pre_roll.append(chunk)

                if self.settings.voice_barge_in and self.barge_detector.is_barge_in(
                    chunk, is_speaking=True
                ):
                    logger.info("User interrupted JARVIS speech. Halting playback...")
                    self._interrupt_event.set()
                    self.speaker.interrupt()
                    interrupted = True
                    if self.on_orb_state:
                        self.on_orb_state("listening")
                    if self.on_status:
                        self.on_status("Interrupted — Listening...")

                    captured_frames.extend(pre_roll)
                    break
        except Exception as exc:
            logger.debug("Error in duplex mic monitoring: %s", exc)

        play_thread.join(timeout=0.5)

        if not interrupted:
            return None

        # Continue recording remainder of user speech until silence
        silent_ms = 0
        unspoken_ms = 0

        for chunk in self.mic.iter_chunks(level_callback=self.on_level):
            if vad.is_speech(chunk):
                captured_frames.append(chunk)
                silent_ms = 0
            else:
                silent_ms += chunk_ms
                captured_frames.append(chunk)

            if silent_ms >= 900 or len(captured_frames) * chunk_ms / 1000 >= 12.0:
                break

        return np.concatenate(captured_frames) if captured_frames else None
