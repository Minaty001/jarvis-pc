"""System Admin Skill — System monitoring, updates, service management."""

from typing import Any

from skills.skill_base import Skill, SkillDefinition, skill_registry
from tools.builtin.shell_exec import run_command


class SystemAdminSkill(Skill):
    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="system_admin",
            description="System admin: updates, services, logs, processes",
            triggers=["update", "upgrade", "service", "process", "log", "system", "reboot", "shutdown"],
            category="system",
        )

    async def execute(self, intent: str, params: dict[str, Any]) -> dict[str, Any]:
        if "update" in intent or "upgrade" in intent:
            return run_command("sudo apt update && sudo apt upgrade -y 2>&1 | tail -5")
        elif "process" in intent:
            return run_command("ps aux --sort=-%cpu | head -10")
        elif "log" in intent:
            return run_command("journalctl -n 20 --no-pager 2>&1 || tail -20 /var/log/syslog 2>&1")
        elif "reboot" in intent:
            return {"success": True, "result": "Reboot request acknowledged. Say 'confirm reboot' to proceed."}
        elif "shutdown" in intent:
            return {"success": True, "result": "Shutdown request acknowledged. Say 'confirm shutdown' to proceed."}

        return {"success": True, "result": "System admin skill active"}


skill_registry.register(SystemAdminSkill())
