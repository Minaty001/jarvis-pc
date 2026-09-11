"""Builtin coding, workspace refactoring, git manipulation, and test runner tools."""

from __future__ import annotations

import logging
import os
import shlex
import subprocess  # nosec B404
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.system.files import atomic_write_text

logger = logging.getLogger(__name__)


def git_status(path: str = ".") -> str:
    """Return the current branch and short git status for the repository at `path`."""
    target_dir = Path(path).resolve()
    try:
        branch_res = subprocess.run(  # nosec B603 B607
            ["git", "-C", str(target_dir), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        status_res = subprocess.run(  # nosec B603 B607
            ["git", "-C", str(target_dir), "status", "--short"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "unknown"
        status = status_res.stdout.strip()
        return f"Branch: {branch}\nStatus:\n{status if status else '(clean)'}"
    except Exception as exc:
        return f"git_status failed: {exc}"


def git_branch(branch_name: str, path: str = ".") -> str:
    """Create and switch to a new git branch in the repository at `path`."""
    target_dir = Path(path).resolve()
    try:
        res = subprocess.run(  # nosec B603 B607
            ["git", "-C", str(target_dir), "checkout", "-b", branch_name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if res.returncode != 0:
            # If branch already exists, try checkout
            res = subprocess.run(  # nosec B603 B607
                ["git", "-C", str(target_dir), "checkout", branch_name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        return res.stdout.strip() or res.stderr.strip() or f"Switched to branch {branch_name}"
    except Exception as exc:
        return f"git_branch failed: {exc}"


def git_diff(path: str = ".") -> str:
    """Return unstaged and staged git diff for the repository at `path`."""
    target_dir = Path(path).resolve()
    try:
        res = subprocess.run(  # nosec B603 B607
            ["git", "-C", str(target_dir), "diff", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        diff_text = res.stdout.strip()
        if not diff_text:
            res_unstaged = subprocess.run(  # nosec B603 B607
                ["git", "-C", str(target_dir), "diff"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            diff_text = res_unstaged.stdout.strip()
        return diff_text or "(No changes in diff)"
    except Exception as exc:
        return f"git_diff failed: {exc}"


def git_commit(message: str, path: str = ".", files: Optional[List[str]] = None) -> str:
    """Stage and commit specified files (or all changes) with `message` in `path`."""
    target_dir = Path(path).resolve()
    try:
        if files:
            add_cmd = ["git", "-C", str(target_dir), "add", "--"] + files
        else:
            add_cmd = ["git", "-C", str(target_dir), "add", "-A"]
        
        subprocess.run(add_cmd, capture_output=True, text=True, timeout=10, check=False)  # nosec B603 B607
        
        commit_res = subprocess.run(  # nosec B603 B607
            ["git", "-C", str(target_dir), "commit", "-m", message],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if commit_res.returncode == 0:
            return f"Committed successfully: {commit_res.stdout.strip()}"
        return f"Commit output ({commit_res.returncode}): {commit_res.stdout.strip() or commit_res.stderr.strip()}"
    except Exception as exc:
        return f"git_commit failed: {exc}"


def replace_file_snippet(file_path: str, target: str, replacement: str) -> str:
    """Replace an exact code snippet `target` with `replacement` in `file_path`."""
    p = Path(file_path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"File '{file_path}' does not exist.")

    content = p.read_text(encoding="utf-8")
    if target not in content:
        raise ValueError(f"Target snippet not found in '{file_path}'.")

    occurrences = content.count(target)
    if occurrences > 1:
        logger.warning("Target snippet occurs %d times in '%s'; replacing all occurrences", occurrences, file_path)

    new_content = content.replace(target, replacement)
    atomic_write_text(p, new_content, encoding="utf-8")
    return f"Successfully updated '{file_path}' ({occurrences} occurrence(s) replaced)."


def run_workspace_tests(
    test_command: str = "pytest",
    path: str = ".",
    timeout: int = 60,
) -> Dict[str, Any]:
    """Execute workspace unit/integration test command and return structured results."""
    target_dir = Path(path).resolve()
    try:
        args = shlex.split(test_command)
        res = subprocess.run(  # nosec B603
            args,
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        passed = (res.returncode == 0)
        return {
            "passed": passed,
            "exit_code": res.returncode,
            "stdout": res.stdout[-2000:],  # Tail last 2000 chars
            "stderr": res.stderr[-2000:],
            "command": test_command,
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Test execution timed out after {timeout} seconds.",
            "command": test_command,
        }
    except Exception as exc:
        return {
            "passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(exc),
            "command": test_command,
        }
