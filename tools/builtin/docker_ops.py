"""Docker Operations."""

import subprocess
from typing import Any

from config.logger import get_logger

logger = get_logger("tools.docker_ops")


def _run(cmd: str) -> dict[str, Any]:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return {"success": result.returncode == 0, "result": result.stdout.strip() or result.stderr.strip() or "OK"}
    except Exception as e:
        return {"success": False, "result": str(e)}


def docker_ps() -> dict[str, Any]:
    return _run("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")


def docker_images() -> dict[str, Any]:
    return _run("docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'")


def docker_start(container: str) -> dict[str, Any]:
    return _run(f"docker start {container}")


def docker_stop(container: str) -> dict[str, Any]:
    return _run(f"docker stop {container}")
