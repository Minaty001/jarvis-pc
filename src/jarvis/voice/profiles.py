"""Voice Profiles, Multi-Accent Neural Voices, and Acoustic Tuning for JARVIS PC."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from jarvis.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class VoiceProfile:
    key: str
    name: str
    voice_id: str
    language: str
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"
    description: str = ""
    persona_tone: str = "butler"
    gender: str = "Male"

    @property
    def voice(self) -> str:
        """Alias for voice_id."""
        return self.voice_id

    @property
    def display_name(self) -> str:
        """Alias for name."""
        return self.name


VOICE_PROFILES: Dict[str, VoiceProfile] = {
    "british_butler": VoiceProfile(
        key="british_butler",
        name="British Butler (Classic J.A.R.V.I.S.)",
        voice_id="en-GB-RyanNeural",
        language="en-GB",
        rate="+0%",
        pitch="-3Hz",
        description="Deep, articulate British butler voice with refined cadence.",
        persona_tone="butler",
        gender="Male",
    ),
    "classic_jarvis": VoiceProfile(
        key="classic_jarvis",
        name="Classic American JARVIS",
        voice_id="en-US-GuyNeural",
        language="en-US",
        rate="+0%",
        pitch="+0Hz",
        description="Crisp, balanced American English assistant tone.",
        persona_tone="butler",
        gender="Male",
    ),
    "tactical_ai": VoiceProfile(
        key="tactical_ai",
        name="Tactical Combat AI",
        voice_id="en-US-ChristopherNeural",
        language="en-US",
        rate="+5%",
        pitch="-4Hz",
        description="Authoritative, crisp tactical system voice.",
        persona_tone="tactical",
        gender="Male",
    ),
    "indian_english": VoiceProfile(
        key="indian_english",
        name="Indian English Executive",
        voice_id="en-IN-PrabhatNeural",
        language="en-IN",
        rate="+0%",
        pitch="+0Hz",
        description="Clear, professional Indian English neural accent.",
        persona_tone="butler",
        gender="Male",
    ),
    "hindi_assistant": VoiceProfile(
        key="hindi_assistant",
        name="Hindi / Hinglish Assistant",
        voice_id="hi-IN-MadhurNeural",
        language="hi-IN",
        rate="+0%",
        pitch="+0Hz",
        description="Natural, warm Hindi neural voice for bilingual interaction.",
        persona_tone="conversational",
        gender="Male",
    ),
    "french_ai": VoiceProfile(
        key="french_ai",
        name="French System AI",
        voice_id="fr-FR-HenriNeural",
        language="fr-FR",
        rate="+0%",
        pitch="+0Hz",
        description="Articulate French male neural voice.",
        persona_tone="butler",
        gender="Male",
    ),
    "german_ai": VoiceProfile(
        key="german_ai",
        name="German System AI",
        voice_id="de-DE-ConradNeural",
        language="de-DE",
        rate="+0%",
        pitch="+0Hz",
        description="Precise German male neural voice.",
        persona_tone="precise",
        gender="Male",
    ),
}

_ACTIVE_PROFILE_KEY = "british_butler"


class VoiceProfileManager:
    """Manages active voice profiles, acoustic tuning, and Edge TTS voice identifiers."""

    def __init__(self, default_key: str = "british_butler", settings=None):
        self.settings = settings if settings is not None else get_settings()
        init_key = getattr(self.settings, "voice_profile", default_key) or default_key
        self.active_key = init_key if init_key in VOICE_PROFILES else "british_butler"

    def set_profile(self, profile_key: str) -> VoiceProfile:
        """Switch active voice profile and sync with settings."""
        global _ACTIVE_PROFILE_KEY
        key = profile_key.strip().lower()
        if key not in VOICE_PROFILES:
            logger.warning("Voice profile '%s' not recognized.", profile_key)
            raise ValueError(f"Unknown voice profile '{profile_key}'. Available: {list(VOICE_PROFILES.keys())}")

        self.active_key = key
        _ACTIVE_PROFILE_KEY = key
        prof = VOICE_PROFILES[key]
        if hasattr(self.settings, "voice_profile"):
            self.settings.voice_profile = key
        if hasattr(self.settings, "voice"):
            self.settings.voice = prof.voice_id
        if hasattr(self.settings, "voice_rate"):
            self.settings.voice_rate = prof.rate
        if hasattr(self.settings, "voice_pitch"):
            self.settings.voice_pitch = prof.pitch
        logger.info("Active voice profile switched to '%s' (%s)", key, prof.voice_id)
        return prof

    def get_profile(self, profile_key: str) -> VoiceProfile:
        """Get profile by key with fallback to default."""
        return VOICE_PROFILES.get(profile_key, VOICE_PROFILES["british_butler"])

    def get_active_profile(self) -> VoiceProfile:
        """Get currently active voice profile."""
        return VOICE_PROFILES.get(self.active_key, VOICE_PROFILES["british_butler"])

    def tune_acoustics(
        self,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        volume: Optional[str] = None,
    ) -> VoiceProfile:
        """Tune acoustic parameters (rate, pitch, volume) for active profile and settings."""
        prof = self.get_active_profile()
        if rate is not None:
            prof.rate = rate
            if hasattr(self.settings, "voice_rate"):
                self.settings.voice_rate = rate
        if pitch is not None:
            prof.pitch = pitch
            if hasattr(self.settings, "voice_pitch"):
                self.settings.voice_pitch = pitch
        if volume is not None:
            prof.volume = volume
        return prof

    def list_profiles(self) -> List[Dict[str, Any]]:
        """List all profile details."""
        res = []
        for k, p in VOICE_PROFILES.items():
            res.append(
                {
                    "key": k,
                    "name": p.name,
                    "display_name": p.display_name,
                    "voice": p.voice_id,
                    "voice_id": p.voice_id,
                    "language": p.language,
                    "rate": p.rate,
                    "pitch": p.pitch,
                    "volume": p.volume,
                    "gender": p.gender,
                    "description": p.description,
                }
            )
        return res


_PROFILE_MANAGER = VoiceProfileManager()


def get_profile_manager() -> VoiceProfileManager:
    return _PROFILE_MANAGER


def get_voice_profile(key: str) -> VoiceProfile:
    return get_profile_manager().get_profile(key)


def list_voice_profiles() -> List[Dict[str, Any]]:
    return get_profile_manager().list_profiles()
