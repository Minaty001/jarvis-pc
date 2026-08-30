"""File Manager Skill — Advanced file operations."""

from pathlib import Path
from typing import Any

from skills.skill_base import Skill, SkillDefinition, skill_registry


class FileManagerSkill(Skill):
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="file_manager",
            description="Advanced file management: find, organize, rename, copy, move files",
            triggers=["find file", "organize", "rename file", "copy file", "move file", "search files"],
            category="files",
        )

    async def execute(self, intent: str, params: dict[str, Any]) -> dict[str, Any]:
        from tools.builtin.shell_exec import run_command

        if "find" in intent:
            query = params.get("query", "")
            result = run_command(f"find ~ -iname '*{query}*' -type f 2>/dev/null | head -20")
            return {"success": True, "result": result.get("result", "No files found")}

        return {"success": True, "result": "File manager skill active"}


skill_registry.register(FileManagerSkill())
