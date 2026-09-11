"""Continuous Background Auto Wake-Word Daemon & Ambient Voice Service."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, List, Optional

import numpy as np

from jarvis.config.settings import Settings, get_settings
from jarvis.voice import vad
from jarvis.voice.duplex import DuplexVoiceSession
from jarvis.voice.microphone import Microphone
from jarvis.voice.stt import transcribe_pcm
from jarvis.voice.tts import speak
from jarvis.voice.wake_word import WakeWordDetector

logger = logging.getLogger(__name__)


class AutoWakeService:
    """Low-power continuous background wake word service with multi-turn conversation support."""

    def __init__(
        self,
        on_command: Optional[Callable[[str], str]] = None,
        on_wake_detected: Optional[Callable[[str], None]] = None,
        on_orb_state: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_chat: Optional[Callable[[str, str], None]] = None,
        on_level: Optional[Callable[[float], None]] = None,
        phrases: Optional[List[str]] = None,
        ack_phrase: Optional[str] = None,
        followup_timeout: Optional[float] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.on_command = on_command
        self.on_wake_detected = on_wake_detected
        self.on_orb_state = on_orb_state
        self.on_status = on_status
        self.on_chat = on_chat
        self.on_level = on_level

        # Wake phrases & acoustics
        if phrases:
            self.phrases = phrases
        else:
            raw_phrases = getattr(self.settings, "wake_phrases", "hey jarvis,jarvis")
            self.phrases = [p.strip() for p in raw_phrases.split(",") if p.strip()]

        self.ack_phrase = (
            ack_phrase
            if ack_phrase is not None
            else getattr(self.settings, "wake_ack_phrase", "Yes, sir?")
        )
        self.followup_timeout = (
            followup_timeout
            if followup_timeout is not None
            else getattr(self.settings, "wake_followup_timeout", 6.0)
        )
        self.vad_threshold = getattr(self.settings, "wake_vad_threshold", 350)

        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._detector: Optional[WakeWordDetector] = None
        self._mic: Optional[Microphone] = None
        self._session: Optional[DuplexVoiceSession] = None

    def start(self) -> bool:
        """Start the background wake word service."""
        if self._running:
            logger.debug("AutoWakeService is already running.")
            return True

        self._running = True
        self._paused = False
        self._thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="jarvis-auto-wake-daemon",
        )
        self._thread.start()
        logger.info("AutoWakeService started with phrases: %s", self.phrases)
        return True

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the background wake word service."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None
        logger.info("AutoWakeService stopped.")

    def pause(self) -> None:
        """Temporarily pause wake word recognition (e.g. during manual typing or modal UI)."""
        self._paused = True
        logger.debug("AutoWakeService paused.")

    def resume(self) -> None:
        """Resume wake word recognition."""
        self._paused = False
        logger.debug("AutoWakeService resumed.")

    @property
    def is_running(self) -> bool:
        return self._running and (self._thread is not None and self._thread.is_alive())

    @property
    def is_paused(self) -> bool:
        return self._paused

    def _notify_orb(self, state: str) -> None:
        if self.on_orb_state:
            try:
                self.on_orb_state(state)
            except Exception as exc:
                logger.debug("on_orb_state error: %s", exc)

    def _notify_status(self, text: str) -> None:
        if self.on_status:
            try:
                self.on_status(text)
            except Exception as exc:
                logger.debug("on_status error: %s", exc)

    def _notify_chat(self, role: str, text: str) -> None:
        if self.on_chat:
            try:
                self.on_chat(role, text)
            except Exception as exc:
                logger.debug("on_chat error: %s", exc)

    def _notify_level(self, level: float) -> None:
        if self.on_level:
            try:
                self.on_level(level)
            except Exception as exc:
                logger.debug("on_level error: %s", exc)

    def _worker_loop(self) -> None:
        """Core background listening loop."""
        try:
            self._detector = WakeWordDetector(phrases=self.phrases)
            self._mic = Microphone()
            self._session = DuplexVoiceSession(
                on_orb_state=self._notify_orb,
                on_status=self._notify_status,
                on_chat=self._notify_chat,
                on_level=self._notify_level,
            )
        except Exception as exc:
            logger.error("Failed to initialize AutoWakeService components: %s", exc, exc_info=True)
            self._running = False
            return

        self._notify_orb("idle")
        self._notify_status("Ambient Wake Word Active ('Hey Jarvis')")

        while self._running:
            if self._paused:
                time.sleep(0.1)
                continue

            try:
                # 1. Listen for wake word with low-power VAD gating
                for chunk in self._mic.iter_chunks():
                    if not self._running:
                        break
                    if self._paused:
                        break

                    # Audio energy calculation
                    energy = float(np.abs(chunk).mean()) if len(chunk) > 0 else 0.0
                    norm_level = min(1.0, energy / 12000.0)
                    self._notify_level(norm_level)

                    # Silence skip (low power mode)
                    if energy < self.vad_threshold:
                        continue

                    # Feed chunk to Vosk Recognizer
                    if self._detector.feed(chunk.tobytes()):
                        logger.info("Wake word detected by AutoWakeService!")
                        if self.on_wake_detected:
                            try:
                                self.on_wake_detected("hey jarvis")
                            except Exception as exc:
                                logger.debug("on_wake_detected callback error: %s", exc)

                        # Trigger full conversational session
                        self._handle_active_conversation()
                        break

            except Exception as exc:
                logger.warning("Error in AutoWakeService loop: %s", exc)
                time.sleep(0.5)

        self._notify_orb("idle")
        self._notify_status("Wake Word Service Inactive")

    def _handle_active_conversation(self) -> None:
        """Handle active conversational turns with follow-up timeout."""
        self._notify_orb("listening")
        self._notify_status("Wake word detected! Listening...")

        # 1. Acknowledgment speech
        if self.ack_phrase and self.ack_phrase.strip():
            voice = getattr(self.settings, "voice", "en-GB-RyanNeural")
            speak(self.ack_phrase, voice=voice)

        interrupted_pcm: Optional[np.ndarray] = None

        while self._running and not self._paused:
            if interrupted_pcm is not None and len(interrupted_pcm) > 0:
                pcm = interrupted_pcm
                interrupted_pcm = None
            else:
                self._notify_orb("listening")
                self._notify_status("Listening for command...")
                pcm = self._mic.record_until_silence(level_callback=self._notify_level)

            if not self._running or self._paused:
                break

            if len(pcm) == 0:
                logger.debug("No speech captured in conversational turn; returning to ambient wake word.")
                break

            self._notify_orb("thinking")
            self._notify_status("Transcribing speech...")

            text = transcribe_pcm(pcm)
            if not text or len(text.strip()) < 2:
                logger.debug("Transcribed speech too short or empty; returning to ambient wake word.")
                break

            logger.info("AutoWake heard command: %r", text)
            self._notify_chat("user", text)

            # 2. Execute command via on_command callback
            reply = "I am on it, sir."
            if self.on_command:
                try:
                    self._notify_status("Executing command...")
                    reply = self.on_command(text)
                except Exception as exc:
                    logger.error("Command execution failed in AutoWake: %s", exc)
                    reply = f"Apologies sir, I encountered an error: {exc}"

            self._notify_chat("assistant", reply)

            # 3. Speak reply with full-duplex barge-in monitoring
            voice = getattr(self.settings, "voice", "en-GB-RyanNeural")
            interrupted_pcm = self._session.speak_and_listen_duplex(reply, voice=voice)

            if interrupted_pcm is not None and len(interrupted_pcm) > 0:
                self._notify_status("User Interrupted — Processing...")
                continue
            else:
                # Prompt finished; listen for follow-up speech within followup_timeout
                self._notify_orb("listening")
                self._notify_status("Awaiting follow-up command...")
                followup_pcm = self._listen_followup(timeout=self.followup_timeout)
                if followup_pcm is not None and len(followup_pcm) > 0:
                    interrupted_pcm = followup_pcm
                    continue
                else:
                    break

        self._notify_orb("idle")
        self._notify_status("Ambient Wake Word Active ('Hey Jarvis')")

    def _listen_followup(self, timeout: float = 6.0) -> Optional[np.ndarray]:
        """Listen for conversational follow-up speech before timing out back to wake word."""
        start_time = time.time()
        for chunk in self._mic.iter_chunks():
            if not self._running or self._paused:
                return None
            if time.time() - start_time > timeout:
                return None

            energy = float(np.abs(chunk).mean()) if len(chunk) > 0 else 0.0
            norm_level = min(1.0, energy / 12000.0)
            self._notify_level(norm_level)

            if vad.is_speech(chunk, threshold=self.vad_threshold):
                # User started speaking! Record complete utterance
                rest_pcm = self._mic.record_until_silence(level_callback=self._notify_level)
                return np.concatenate([chunk, rest_pcm]) if len(rest_pcm) > 0 else chunk

        return None
