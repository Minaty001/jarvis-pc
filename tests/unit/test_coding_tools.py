"""Unit tests for builtin coding tools (git helpers, file replacers, test runner)."""

from __future__ import annotations

import subprocess
from pathlib import Path
import pytest

from jarvis.tools.builtin.coding import (
    git_branch,
    git_commit,
    git_diff,
    git_status,
    replace_file_snippet,
    run_workspace_tests,
)


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Initialize a clean git repo in a temp directory for safe testing."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "TestUser"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)

    test_file = repo / "main.py"
    test_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial commit"], check=True)
    return repo


def test_git_status_and_branch(temp_git_repo: Path):
    status = git_status(str(temp_git_repo))
    assert "(clean)" in status or "Branch:" in status

    branch_out = git_branch("jarvis/test-feature", str(temp_git_repo))
    assert "jarvis/test-feature" in branch_out or "Switched to branch" in branch_out

    status_after = git_status(str(temp_git_repo))
    assert "jarvis/test-feature" in status_after


def test_replace_file_snippet(temp_git_repo: Path):
    test_file = temp_git_repo / "main.py"
    res = replace_file_snippet(
        str(test_file),
        target="return 'world'",
        replacement="return 'universe'",
    )
    assert "Successfully updated" in res
    assert "return 'universe'" in test_file.read_text(encoding="utf-8")


def test_replace_file_snippet_missing_target(temp_git_repo: Path):
    test_file = temp_git_repo / "main.py"
    with pytest.raises(ValueError, match="Target snippet not found"):
        replace_file_snippet(str(test_file), "non_existent_code", "new_code")


def test_git_diff_and_commit(temp_git_repo: Path):
    test_file = temp_git_repo / "main.py"
    test_file.write_text("def hello():\n    return 'galaxy'\n", encoding="utf-8")

    diff = git_diff(str(temp_git_repo))
    assert "+    return 'galaxy'" in diff

    commit_res = git_commit("feat: update greeting", str(temp_git_repo))
    assert "Committed successfully" in commit_res


def test_run_workspace_tests_pass(tmp_path: Path):
    res = run_workspace_tests("python3 -c 'exit(0)'", path=str(tmp_path))
    assert res["passed"] is True
    assert res["exit_code"] == 0


def test_run_workspace_tests_fail(tmp_path: Path):
    res = run_workspace_tests("python3 -c 'import sys; sys.stderr.write(\"error\"); exit(1)'", path=str(tmp_path))
    assert res["passed"] is False
    assert res["exit_code"] == 1
    assert "error" in res["stderr"]
