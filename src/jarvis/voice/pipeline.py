"""High-level voice pipeline: listen once, wait for wake word, full session."""

from __future__ import annotations

from typing import Callable

from jarvis.config.settings import get_settings
from jarvis.voice import stt
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
    """Idle wake-word loop; routes recognized speech to `on_command`, reads reply aloud."""
    voice = get_settings().voice
    while True:
        wait_for_wake()
        speak("Yes, sir?", voice)
        command = listen_once()
        if not command:
            speak("I did not catch that. Say it again, sir.", voice)
            continue
        reply = on_command(command)
        speak(reply or "Done, sir.", voice)