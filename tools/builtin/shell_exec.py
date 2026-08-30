"""Shell Execution — Run system commands."""

import subprocess
from typing import Any

from config.logger import get_logger

logger = get_logger("tools.shell_exec")


def run_command(command: str) -> dict[str, Any]:
    """Execute a shell command and return output."""
    logger.info("Executing: %s", command)
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            output = result.stderr.strip() or output
            return {
                "success": result.returncode == 0,
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
