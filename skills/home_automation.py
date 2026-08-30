"""Smart Home Skill — Home Assistant integration."""

import httpx
from typing import Any

from config.logger import get_logger
from config.settings import settings
from skills.skill_base import Skill, SkillDefinition, skill_registry

logger = get_logger("skills.home_automation")


class HomeAutomationSkill(Skill):
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="home_automation",
            description="Smart home control via Home Assistant",
            triggers=["lights", "turn on", "turn off", "thermostat", "temperature", "smart home"],
            category="automation",
        )

    async def execute(self, intent: str, params: dict[str, Any]) -> dict[str, Any]:
        if not settings.home_assistant_url:
            return {"success": False, "result": "Home Assistant not configured"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {
                    "Authorization": f"Bearer {settings.home_assistant_token}",
                    "Content-Type": "application/json",
                }
                resp = await client.get(
                    f"{settings.home_assistant_url}/api/states",
                    headers=headers,
                )
                resp.raise_for_status()
                states = resp.json()

                entities = [s["entity_id"] for s in states[:10]]
                return {"success": True, "result": f"Smart home entities: {', '.join(entities)}"}
        except Exception as e:
            return {"success": False, "result": f"Home Assistant error: {e}"}


skill_registry.register(HomeAutomationSkill())
