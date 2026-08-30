"""
Skill Base — Interface and registry for all Jarvis skills.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from config.logger import get_logger

logger = get_logger("skills.base")


@dataclass
class SkillDefinition:
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    category: str = "general"


class Skill(ABC):
    """Base class for all Jarvis skills."""

    @property
    @abstractmethod
    def definition(self) -> SkillDefinition:
        ...

    @abstractmethod
    async def execute(self, intent: str, params: dict[str, Any]) -> dict[str, Any]:
        ...

    def matches(self, text: str) -> bool:
        """Check if this skill matches the user's intent."""
        text_lower = text.lower()
        return any(trigger in text_lower for trigger in self.definition.triggers)


class SkillRegistry:
    """Registry of all available skills."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.definition.name] = skill
        logger.info("Registered skill: %s", skill.definition.name)

    def find(self, text: str) -> Optional[Skill]:
        """Find the best matching skill for user input."""
        for skill in self._skills.values():
            if skill.matches(text):
                return skill
        return None

    def list_skills(self) -> list[SkillDefinition]:
        return [s.definition for s in self._skills.values()]

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)


skill_registry = SkillRegistry()
