"""Web Research Skill — Search, fetch, summarize web content."""

from typing import Any

from skills.skill_base import Skill, SkillDefinition, skill_registry


class WebResearchSkill(Skill):
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="web_research",
            description="Web research: search, fetch pages, summarize articles",
            triggers=["search", "look up", "research", "find online", "google", "what is"],
            category="web",
        )

    async def execute(self, intent: str, params: dict[str, Any]) -> dict[str, Any]:
        from tools.builtin.web_search import web_search

        query = params.get("query", intent)
        return await web_search(query)


skill_registry.register(WebResearchSkill())
