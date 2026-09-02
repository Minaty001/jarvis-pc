"""Shell Execution — Run system commands."""

import shlex
import subprocess
from typing import Any

from config.logger import get_logger

logger = get_logger("tools.shell_exec")


def run_command(command: str) -> dict[str, Any]:
    """Execute a system command safely without shell execution."""
    logger.info("Executing: %s", command)
    try:
        cmd_args = shlex.split(command) if isinstance(command, str) else command
        if not cmd_args:
            return {"success": False, "result": "Empty command provided"}
        result = subprocess.run(
            cmd_args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            output = result.stderr.strip() or output
            return {
                "success": False,
                "result": output or "Command executed (no output)",
                "returncode": result.returncode,
            }
        return {
            "success": True,
            "result": output or "Command executed successfully",
            "returncode": 0,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "result": "Command timed out (30s limit)"}
    except Exception as e:
        return {"success": False, "result": f"Command failed: {e}"}

