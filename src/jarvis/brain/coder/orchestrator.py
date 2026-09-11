"""Multi-Agent Coding & Autonomous Workspace Copilot Orchestrator."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.brain.client import LLMClient
from jarvis.tools.builtin.coding import (
    git_branch,
    git_commit,
    git_diff,
    git_status,
    replace_file_snippet,
    run_workspace_tests,
)
from jarvis.system.files import atomic_write_text

logger = logging.getLogger(__name__)


@dataclass
class CodingTaskResult:
    success: bool
    task: str
    branch: str
    plan: str
    files_modified: List[str] = field(default_factory=list)
    test_results: Optional[Dict[str, Any]] = None
    commit_info: Optional[str] = None
    diff: str = ""
    error: Optional[str] = None
    iterations: int = 1


class CodingCopilot:
    """Orchestrates Architect, Engineer, and QA/Reviewer agents for autonomous codebase tasks."""

    def __init__(self, llm_client: Optional[LLMClient] = None, max_retries: int = 3):
        self.llm = llm_client or LLMClient()
        self.max_retries = max_retries

    async def plan_task(self, task: str, workspace: Path) -> Dict[str, Any]:
        """Architect phase: analyze task and propose plan, file changes, and test command."""
        status_text = git_status(str(workspace))
        prompt = (
            f"You are an expert Software Architect.\n"
            f"Task: {task}\n"
            f"Workspace Path: {workspace}\n"
            f"Current Git Status:\n{status_text}\n\n"
            "Produce an actionable architectural plan in JSON format with exactly these keys:\n"
            "{\n"
            '  "summary": "High level strategy",\n'
            '  "branch_name": "jarvis/feature-or-fix-name",\n'
            '  "files_to_modify": ["path/to/file1.py"],\n'
            '  "files_to_create": ["path/to/new_file.py"],\n'
            '  "test_command": "pytest tests/unit/test_new_feature.py"\n'
            "}\n"
            "Return ONLY the JSON object, nothing else."
        )
        try:
            response = await self.llm.complete(prompt)
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as exc:
            logger.warning("Architect JSON parse failed (%s); using fallback plan", exc)

        slug = re.sub(r"[^a-zA-Z0-9]+", "-", task.lower()).strip("-")[:30] or "task"
        return {
            "summary": f"Execute coding task: {task}",
            "branch_name": f"jarvis/{slug}",
            "files_to_modify": [],
            "files_to_create": [],
            "test_command": "pytest",
        }

    async def execute_task(
        self,
        task: str,
        workspace_path: str = ".",
        auto_commit: bool = True,
    ) -> CodingTaskResult:
        """Run the full Architect -> Engineer -> QA loop with auto-retry."""
        workspace = Path(workspace_path).resolve()
        plan_dict = await self.plan_task(task, workspace)
        branch_name = plan_dict.get("branch_name", "jarvis/copilot-task")

        logger.info("Creating feature branch '%s' for task", branch_name)
        git_branch(branch_name, str(workspace))

        test_command = plan_dict.get("test_command", "pytest")
        files_modified: List[str] = []
        iteration = 0
        last_test_result: Optional[Dict[str, Any]] = None

        while iteration < self.max_retries:
            iteration += 1
            logger.info("Starting Copilot iteration %d/%d", iteration, self.max_retries)

            # Engineer phase: Generate file modifications or fixes
            engineer_prompt = (
                f"You are an expert Software Engineer.\n"
                f"Goal: {task}\n"
                f"Architect Plan: {plan_dict.get('summary')}\n"
                f"Workspace: {workspace}\n"
            )
            if last_test_result and not last_test_result.get("passed"):
                engineer_prompt += (
                    f"\nPrevious test execution FAILED with:\n"
                    f"STDOUT:\n{last_test_result.get('stdout', '')}\n"
                    f"STDERR:\n{last_test_result.get('stderr', '')}\n"
                    f"Please fix the code or tests to resolve this error.\n"
                )

            engineer_prompt += (
                "\nSpecify the files to create or update in valid JSON format:\n"
                "{\n"
                '  "actions": [\n'
                '     {"action": "write", "path": "path/file.py", "content": "file code here"}\n'
                "  ]\n"
                "}\n"
                "Return ONLY the JSON object."
            )

            try:
                eng_response = await self.llm.complete(engineer_prompt)
                match = re.search(r"\{.*\}", eng_response, re.DOTALL)
                if match:
                    actions_data = json.loads(match.group(0))
                    for act in actions_data.get("actions", []):
                        rel_path = act.get("path")
                        content = act.get("content", "")
                        if rel_path and content:
                            target = (workspace / rel_path).resolve()
                            target.parent.mkdir(parents=True, exist_ok=True)
                            atomic_write_text(target, content, encoding="utf-8")
                            if rel_path not in files_modified:
                                files_modified.append(rel_path)
            except Exception as exc:
                logger.warning("Engineer file writing failed (%s)", exc)

            # QA / Reviewer Phase: Run tests
            logger.info("QA running test command: '%s'", test_command)
            last_test_result = run_workspace_tests(test_command, path=str(workspace))

            if last_test_result.get("passed", False):
                logger.info("QA verified: all tests passed successfully!")
                break

        # Verification & Commit
        diff = git_diff(str(workspace))
        commit_info = None
        is_success = bool(last_test_result and last_test_result.get("passed", False))

        if is_success and auto_commit:
            commit_msg = f"feat: {task[:50]} (JARVIS Copilot verified)"
            commit_info = git_commit(commit_msg, str(workspace))

        return CodingTaskResult(
            success=is_success,
            task=task,
            branch=branch_name,
            plan=plan_dict.get("summary", ""),
            files_modified=files_modified,
            test_results=last_test_result,
            commit_info=commit_info,
            diff=diff,
            iterations=iteration,
            error=None if is_success else "Tests failed after maximum retries.",
        )
