"""Media Player Skill — Music, video, streaming control."""

from typing import Any

from skills.skill_base import Skill, SkillDefinition, skill_registry


class MediaPlayerSkill(Skill):
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="media_player",
            description="Media playback: play, pause, volume, music search",
            triggers=["play", "pause", "music", "video", "volume", "mute", "song"],
            category="media",
        )

    async def execute(self, intent: str, params: dict[str, Any]) -> dict[str, Any]:
        from tools.builtin import media_control

        if "pause" in intent or "stop" in intent:
            return media_control.media_pause()
        elif "play" in intent:
            query = params.get("query", params.get("name", ""))
            return media_control.media_play(query)
        elif "volume" in intent:
            level = params.get("level", "50")
            return media_control.set_volume(str(level))
        elif "mute" in intent:
            return media_control.set_volume("0")

        return {"success": True, "result": "Media player skill active"}


skill_registry.register(MediaPlayerSkill())
