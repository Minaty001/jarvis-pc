"""
Security Policy — Gates all tool execution with risk levels, confirmations, and audit.
Never allows arbitrary model output to directly execute shell/system actions.
"""

import time
from typing import Any, Optional

from config.logger import get_logger
from tools.registry import ToolDef, RiskLevel, ToolCategory, tool_registry

logger = get_logger("security.policy")


class SecurityPolicy:
    """Evaluates and enforces security rules for tool execution."""

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self._audit_log: list[dict] = []
        self._blocked_patterns: list[str] = [
            "rm -rf /",
            "dd if=",
            "mkfs",
            "> /dev/sda",
            ":(){ :|:& };:",
            "chmod -R 777 /",
            "wget.*|.*sh",
            "curl.*|.*sh",
        ]
        self._allowed_commands: set[str] = set()
        self._denied_commands: set[str] = set()

    def evaluate(self, tool: ToolDef, args: dict, user_context: Optional[dict] = None) -> tuple[bool, str, str]:
        """
        Evaluate whether a tool call is allowed.
        Returns (allowed, reason, risk_override).
        """
        risk = tool.risk_level

        # Check blocked patterns in arguments
        args_str = str(args).lower()
        for pattern in self._blocked_patterns:
            if pattern.lower() in args_str:
                self._audit("blocked_pattern", tool.name, args, pattern)
                return False, f"Blocked dangerous pattern: {pattern}", ""

        # Deterministic Risk Determination from Tool & Arguments (never trust model risk)
        command_str = str(args.get("command", "")).lower()
        if tool.name == "run_command":
            if any(danger in command_str for danger in ("rm ", "mkfs", "dd ", "chmod ", "chown ", "sudo ", "pkill -f")):
                risk = RiskLevel.CRITICAL
            else:
                risk = RiskLevel.HIGH

        # Risk-based checks
        if risk == RiskLevel.CRITICAL:
            if user_context and user_context.get("confirmed", False):
                self._audit("critical_confirmed", tool.name, args)
                return True, "Critical risk confirmed by user", ""
            self._audit("critical_requires_confirmation", tool.name, args)
            return False, "Critical risk tool requires explicit user confirmation", ""

        if risk == RiskLevel.HIGH:
            if tool.requires_confirmation and not (user_context and user_context.get("confirmed", False)):
                self._audit("high_risk_pending_confirmation", tool.name, args)
                return False, "High risk tool requires user confirmation", ""

        if risk == RiskLevel.MEDIUM and tool.requires_permission:
            pass

        # Command-specific checks for system tools
        if tool.category == ToolCategory.SYSTEM:
            cmd = args.get("command", "")
            if cmd:
                cmd_check = self._check_command(cmd)
                if not cmd_check[0]:
                    self._audit("command_blocked", tool.name, args, cmd_check[1])
                    return False, cmd_check[1], ""

        self._audit("allowed", tool.name, args)
        return True, "Allowed", ""

    def _check_command(self, cmd: str) -> tuple[bool, str]:
        """Check a shell command for safety."""
        cmd_lower = cmd.lower().strip()

        # Check denied commands
        for denied in self._denied_commands:
            if denied in cmd_lower:
                return False, f"Command contains denied pattern: {denied}"

        # Check blocked patterns
        for pattern in self._blocked_patterns:
            if pattern.lower() in cmd_lower:
                return False, f"Command matches blocked pattern: {pattern}"

        # Block pipe to shell execution
        if "| sh" in cmd_lower or "| bash" in cmd_lower:
            return False, "Piping to shell is not allowed"

        # Block background execution of dangerous commands
        dangerous = ["rm ", "dd ", "mkfs", "shutdown", "reboot", "init "]
        for d in dangerous:
            if d in cmd_lower and "&" in cmd_lower:
                return False, f"Cannot run '{d.strip()}' in background"

        return True, ""

    def _audit(self, action: str, tool_name: str, args: dict, detail: str = "") -> None:
        """Log security-relevant decisions."""
        entry = {
            "time": time.time(),
            "action": action,
            "tool": tool_name,
            "args_summary": str(args)[:200],
            "detail": detail,
        }
        self._audit_log.append(entry)
        if len(self._audit_log) > 2000:
            self._audit_log = self._audit_log[-2000:]

        if action in ("blocked_pattern", "critical_blocked", "command_blocked"):
            logger.warning("SECURITY: %s on %s: %s", action, tool_name, detail)
        else:
            logger.debug("SECURITY: %s on %s", action, tool_name)

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        """Get recent audit log entries."""
        return self._audit_log[-limit:]

    def add_blocked_pattern(self, pattern: str) -> None:
        self._blocked_patterns.append(pattern)

    def add_denied_command(self, command: str) -> None:
        self._denied_commands.add(command)

    def get_summary(self) -> str:
        blocked = sum(1 for e in self._audit_log if "blocked" in e["action"])
        allowed = sum(1 for e in self._audit_log if e["action"] == "allowed")
        return f"Allowed: {allowed} | Blocked: {blocked} | Patterns: {len(self._blocked_patterns)}"


security_policy = SecurityPolicy()
