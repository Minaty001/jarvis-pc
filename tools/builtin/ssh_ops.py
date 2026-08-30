"""SSH Operations — Remote execution."""

import subprocess
from typing import Any

from config.logger import get_logger

logger = get_logger("tools.ssh_ops")


def ssh_exec(host: str, command: str, user: str = "root") -> dict[str, Any]:
    """Execute command on remote host via SSH."""
    try:
        result = subprocess.run(
            ["ssh", f"{user}@{host}", command],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "success": result.returncode == 0,
            "result": result.stdout.strip() or result.stderr.strip() or "OK",
        }
    except Exception as e:
        return {"success": False, "result": f"SSH failed: {e}"}
