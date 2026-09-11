"""High-level voice pipeline: listen once, wait for wake word, full session."""

from __future__ import annotations

import logging
from typing import Callable

from jarvis.config.settings import get_settings

logger = logging.getLogger(__name__)
from jarvis.voice import stt
from jarvis.voice.duplex import DuplexVoiceSession
from jarvis.voice.microphone import Microphone
from jarvis.voice.tts import speak
from jarvis.voice.wake_word import WakeWordDetector


def listen_once() -> str:
    """Record until silence and transcribe what was said (Groq → Vosk fallback)."""
    pcm = Microphone().record_until_silence()
    if len(pcm) == 0:
        return ""
    return stt.transcribe(stt.wav_at_16k(pcm, 16000))


def wait_for_wake(phrases: list[str] | None = None) -> None:
    """Block until a wake phrase is spoken."""
    detector = WakeWordDetector(phrases)
    for chunk in Microphone().iter_chunks():
        if detector.feed(chunk.tobytes()):
            return


def voice_loop(on_command: Callable[[str], str]) -> None:
    """Idle wake-word loop; routes recognized speech to `on_command`, reads reply aloud with barge-in interruption."""
    settings = get_settings()
    voice = settings.voice
    session = DuplexVoiceSession()

    while True:
        wait_for_wake()
        speak("Yes, sir?", voice)
        
        command = listen_once()
        while command:
            reply = on_command(command)
            # Full-duplex speech output: if interrupted, user_pcm contains the new command
            user_pcm = session.speak_and_listen_duplex(reply or "Done, sir.", voice)
            if user_pcm is not None and len(user_pcm) > 0:
                # Interrupted by user! Process the interrupted command immediately without waiting for wake word
                command = stt.transcribe(stt.wav_at_16k(user_pcm, 16000))
            else:
                command = ""


def run_auto_wake_service(
    on_command: Callable[[str], str],
    phrases: list[str] | None = None,
    ack_phrase: str | None = None,
) -> None:
    """Run continuous AutoWakeService blocking until interrupted."""
    import time
    from jarvis.voice.auto_wake import AutoWakeService

    service = AutoWakeService(
        on_command=on_command,
        phrases=phrases,
        ack_phrase=ack_phrase,
    )
    service.start()
    try:
        while service.is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("AutoWakeService interrupted by user.")
    finally:
        service.stop()