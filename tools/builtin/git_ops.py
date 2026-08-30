"""Git Operations."""

import subprocess
from typing import Any

from config.logger import get_logger

logger = get_logger("tools.git_ops")


def _run(cmd: str) -> dict[str, Any]:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return {"success": result.returncode == 0, "result": result.stdout.strip() or result.stderr.strip() or "OK"}
    except Exception as e:
        return {"success": False, "result": str(e)}


def git_status() -> dict[str, Any]:
    return _run("git status --short")


def git_commit(message: str) -> dict[str, Any]:
    _run("git add -A")
    return _run(f'git commit -m "{message}"')


def git_push() -> dict[str, Any]:
    return _run("git push")


def git_pull() -> dict[str, Any]:
    return _run("git pull")
