"""Developer Tools Skill — Code, git, docker, build tools."""

from typing import Any

from skills.skill_base import Skill, SkillDefinition, skill_registry


class DevToolsSkill(Skill):
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="dev_tools",
            description="Developer tools: code editing, git, docker, build, test",
            triggers=["code", "git", "docker", "build", "test", "compile", "deploy", "debug"],
            category="development",
        )

    async def execute(self, intent: str, params: dict[str, Any]) -> dict[str, Any]:
        from tools.builtin import git_ops, docker_ops, shell_exec

        if "git status" in intent:
            return git_ops.git_status()
        elif "git commit" in intent:
            msg = params.get("message", "update")
            return git_ops.git_commit(msg)
        elif "git push" in intent:
            return git_ops.git_push()
        elif "docker" in intent and "container" in intent:
            return docker_ops.docker_ps()
        elif "build" in intent or "compile" in intent:
            return shell_exec.run_command("make build 2>&1 || echo 'No Makefile found'")
        elif "test" in intent:
            return shell_exec.run_command("pytest 2>&1 || python -m pytest 2>&1 || echo 'No test runner found'")

        return {"success": True, "result": "Dev tools skill active"}


skill_registry.register(DevToolsSkill())
