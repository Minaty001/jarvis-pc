"""Unit tests for multi-agent Copilot orchestrator."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from jarvis.brain.coder.orchestrator import CodingCopilot


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "copilot_repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "TestUser"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    init_file = repo / "lib.py"
    init_file.write_text("def add(a, b): return a + b\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True)
    return repo


@pytest.mark.asyncio
async def test_copilot_execute_task_success(temp_git_repo: Path):
    mock_llm = MagicMock()

    # Step 1 response (Architect)
    plan_json = json.dumps({
        "summary": "Add multiply function and unit test",
        "branch_name": "jarvis/feat-multiply",
        "files_to_modify": [],
        "files_to_create": ["tests/test_calc.py"],
        "test_command": "python3 -c 'exit(0)'",
    })

    # Step 2 response (Engineer)
    engineer_json = json.dumps({
        "actions": [
            {
                "action": "write",
                "path": "calc.py",
                "content": "def multiply(a, b): return a * b\n"
            }
        ]
    })

    mock_llm.complete = AsyncMock(side_effect=[plan_json, engineer_json])

    copilot = CodingCopilot(llm_client=mock_llm, max_retries=2)
    result = await copilot.execute_task(
        "Add multiply function",
        workspace_path=str(temp_git_repo),
        auto_commit=True,
    )

    assert result.success is True
    assert result.branch == "jarvis/feat-multiply"
    assert "calc.py" in result.files_modified
    assert (temp_git_repo / "calc.py").exists()
    assert result.commit_info is not None
