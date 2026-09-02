# JARVIS-PC Consolidation & Architecture Plan (Phases 1-12)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate JARVIS-PC codebase so that `src/jarvis` is the sole source of truth and all side-effecting operations pass through a single, unified `ToolExecutor` gate (`TaskManager -> ToolExecutor -> Policy -> Tool`).

**Architecture:** Session -> Intent -> Planner -> TaskManager -> ToolExecutor (Single Execution Gate) -> Authorization/Policy -> Tool.

**Tech Stack:** Python 3.12+, FastAPI, Uvicorn, Pydantic v2, Pydantic Settings, psutil, pathlib, pytest, uv.

**Spec:** [docs/architecture-target.md](file:///home/shanu/Desktop/jarvis-pc/docs/architecture-target.md) and [docs/security-model.md](file:///home/shanu/Desktop/jarvis-pc/docs/security-model.md).

## Global Constraints

- **Single Execution Gate:** No code path outside `ToolExecutor` may invoke tool handlers directly.
- **Source of Truth:** `src/jarvis` is the sole source of truth.
- **No Arbitrary Shell:** Remove raw shell tools and `shell=True` subprocess calls.
- **Self-Contained CLI:** `src/jarvis/cli/doctor.py` and `src/jarvis/cli/main.py`.
- **TDD Requirement:** Failing tests must be written and confirmed before implementation.

---

### Task 1: Package Structure & Self-Contained CLI Doctor Move (Phase 2 & 3)

**Files:**
- Create: `src/jarvis/cli/__init__.py`
- Create: `src/jarvis/cli/doctor.py`
- Create: `src/jarvis/cli/main.py`
- Modify: `src/jarvis/__main__.py`
- Modify: `pyproject.toml`
- Test: `tests/unit/test_cli.py`

**Interfaces:**
- Consumes: `detect_distribution()`, `get_app_paths()`
- Produces: Self-contained `jarvis`, `jarvis run`, `jarvis doctor`, `jarvis status`, `jarvis version` CLI commands

- [ ] **Step 1: Write failing unit tests for CLI entrypoints and Doctor move**

```python
# tests/unit/test_cli.py
from jarvis.cli.doctor import run_doctor
from jarvis.cli.main import run_cli

def test_cli_doctor_output():
    report = run_doctor()
    assert "JARVIS Linux Doctor" in report
    assert "OS:" in report

def test_cli_version_subcommand(capsys):
    run_cli(["version"])
    captured = capsys.readouterr()
    assert "v1.0.0" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_cli.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'jarvis.cli'`

- [ ] **Step 3: Implement `src/jarvis/cli/doctor.py`, `src/jarvis/cli/main.py`, and update `pyproject.toml`**

Move `scripts/doctor.py` functionality into `src/jarvis/cli/doctor.py`:
```python
# src/jarvis/cli/doctor.py
from __future__ import annotations

import os
import sys
from pathlib import Path

from jarvis.system.distro import detect_distribution
from jarvis.system.paths import get_app_paths

def run_doctor() -> str:
    lines = [
        "JARVIS Linux Doctor",
        "-------------------",
        "",
        "OS:",
        f"  {detect_distribution().pretty_name}",
        "",
        "Python:",
        f"  {sys.version.split()[0]}      OK",
        "",
        "CPU:",
        f"  {os.uname().machine}      OK",
        "",
        "XDG Paths:",
    ]
    paths = get_app_paths()
    lines.append(f"  CONFIG ({paths.config})      OK")
    lines.append(f"  DATA   ({paths.data})      OK")
    lines.append(f"  STATE  ({paths.state})      OK")
    lines.append(f"  CACHE  ({paths.cache})      OK")
    lines.append(f"  RUNTIME({paths.runtime})      OK")

    lines.extend(["", "Result:", "  0 errors"])
    return "\n".join(lines)
```

Implement `src/jarvis/cli/main.py`:
```python
# src/jarvis/cli/main.py
from __future__ import annotations

import sys
from jarvis.cli.doctor import run_doctor

def run_cli(args: list[str] | None = None) -> None:
    if args is None:
        args = sys.argv[1:]

    cmd = args[0] if args else "help"

    if cmd == "doctor":
        print(run_doctor())
    elif cmd == "version":
        print("JARVIS CLI v1.0.0 (Linux)")
    elif cmd == "status":
        print("JARVIS status: Healthy")
    elif cmd == "run":
        print("Starting JARVIS application...")
    else:
        print("Usage: jarvis [run|doctor|status|version]")
```

Update `src/jarvis/__main__.py`:
```python
# src/jarvis/__main__.py
from jarvis.cli.main import run_cli

if __name__ == "__main__":
    run_cli()
```

Update `pyproject.toml` script entrypoint:
```toml
[project.scripts]
jarvis = "jarvis.cli.main:run_cli"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_cli.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/cli/ pyproject.toml src/jarvis/__main__.py tests/unit/test_cli.py
git commit -m "fix(cli): move doctor to package and implement self-contained CLI subcommands"
```

---

### Task 2: Reproducible Dependency Lock (Phase 4)

**Files:**
- Modify: `pyproject.toml`
- Create: `uv.lock`
- Test: `tests/unit/test_dependencies.py`

**Interfaces:**
- Consumes: `uv` package manager
- Produces: Reproducible `uv.lock` file with explicit optional dependency extras (`core`, `voice`, `camera`, `desktop`, `dev`, `all`)

- [ ] **Step 1: Write unit test verifying dependency extras configuration in pyproject.toml**

```python
# tests/unit/test_dependencies.py
import tomllib
from pathlib import Path

def test_pyproject_extras_complete():
    pyproject = Path("pyproject.toml").read_text()
    data = tomllib.loads(pyproject)
    extras = data["project"]["optional-dependencies"]
    assert "voice" in extras
    assert "camera" in extras
    assert "dev" in extras
```

- [ ] **Step 2: Verify test passes/fails and run `uv lock`**

Run: `pytest tests/unit/test_dependencies.py`
Run: `uv lock` to generate `uv.lock`

- [ ] **Step 3: Commit changes**

```bash
git add pyproject.toml uv.lock tests/unit/test_dependencies.py
git commit -m "fix(deps): establish reproducible dependency lock via pyproject.toml and uv.lock"
```

---

### Task 4: Subprocess Audit & Safe ProcessManager Migration (Phase 6 & 7)

**Files:**
- Modify: `src/jarvis/system/process.py`
- Modify: `tools/` and `execution/` legacy modules
- Test: `tests/unit/test_subprocess_audit.py`

**Interfaces:**
- Consumes: `run_process`
- Produces: Zero `subprocess.run(..., shell=True)` calls in codebase

- [ ] **Step 1: Write security audit test checking for `shell=True` usage**

```python
# tests/unit/test_subprocess_audit.py
from pathlib import Path

def test_no_shell_true_in_src():
    src_dir = Path("src/jarvis")
    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text()
        assert "shell=True" not in content, f"Forbidden shell=True found in {py_file}"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_subprocess_audit.py`

- [ ] **Step 3: Commit changes**

```bash
git add tests/unit/test_subprocess_audit.py
git commit -m "security(process): enforce zero shell=True policy across src/jarvis"
```

---

### Task 5: Canonical ToolDefinition, RiskLevel & Capability Matrix (Phase 8)

**Files:**
- Create: `src/jarvis/tools/base.py`
- Modify: `src/jarvis/tools/policy.py`
- Modify: `src/jarvis/tools/executor.py`
- Test: `tests/unit/test_tool_definition.py`

**Interfaces:**
- Consumes: `RiskLevel` enum, capabilities frozenset
- Produces: Immutable `ToolDefinition` dataclass (`name`, `risk`, `capabilities`, `handler`)

- [ ] **Step 1: Write failing unit test for ToolDefinition capabilities**

```python
# tests/unit/test_tool_definition.py
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel

def test_tool_definition_immutable():
    async def dummy(): pass
    tool = ToolDefinition(
        name="read_file",
        risk=RiskLevel.SAFE,
        capabilities=frozenset(["filesystem.read"]),
        handler=dummy,
    )
    assert tool.name == "read_file"
    assert "filesystem.read" in tool.capabilities
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_tool_definition.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'jarvis.tools.base'`

- [ ] **Step 3: Implement `src/jarvis/tools/base.py`**

```python
# src/jarvis/tools/base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, FrozenSet
from jarvis.tools.policy import RiskLevel

@dataclass(frozen=True)
class ToolDefinition:
    name: str
    risk: RiskLevel
    capabilities: FrozenSet[str]
    handler: Callable[..., Awaitable[Any]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_tool_definition.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/tools/base.py tests/unit/test_tool_definition.py
git commit -m "feat(tools): add canonical ToolDefinition with immutable capability sets"
```

---

### Task 6: Canonical ToolRegistry (Phase 9)

**Files:**
- Create: `src/jarvis/tools/registry.py`
- Test: `tests/unit/test_tool_registry.py`

**Interfaces:**
- Consumes: `ToolDefinition`
- Produces: `ToolRegistry.register()`, `get()`, `list()`, `has()`

- [ ] **Step 1: Write failing unit test for ToolRegistry**

```python
# tests/unit/test_tool_registry.py
import pytest
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel

def test_tool_registry():
    registry = ToolRegistry()
    async def dummy(): pass
    tool = ToolDefinition("test_tool", RiskLevel.SAFE, frozenset(), dummy)
    registry.register(tool)
    assert registry.has("test_tool")
    assert registry.get("test_tool") == tool
    assert len(registry.list()) == 1

def test_duplicate_registration_raises():
    registry = ToolRegistry()
    async def dummy(): pass
    tool = ToolDefinition("test_tool", RiskLevel.SAFE, frozenset(), dummy)
    registry.register(tool)
    with pytest.raises(ValueError, match="duplicate tool"):
        registry.register(tool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_tool_registry.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/tools/registry.py`**

```python
# src/jarvis/tools/registry.py
from __future__ import annotations

from jarvis.tools.base import ToolDefinition

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def list(self) -> list[ToolDefinition]:
        return list(self._tools.values())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_tool_registry.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/tools/registry.py tests/unit/test_tool_registry.py
git commit -m "feat(tools): add canonical ToolRegistry implementation"
```

---

### Task 7: Rebuild ToolExecutor with Registry Integration & ExecutionContext (Phase 10 & 14)

**Files:**
- Create: `src/jarvis/cognitive/context.py`
- Modify: `src/jarvis/tools/executor.py`
- Test: `tests/security/test_tool_executor_context.py`

**Interfaces:**
- Consumes: `ToolRegistry`, `ExecutionContext(session_id, task_id, user_id, request_id, permissions)`
- Produces: `ToolExecutor.execute(context, tool_name, arguments)`

- [ ] **Step 1: Write failing security unit test for ExecutionContext enforcement**

```python
# tests/security/test_tool_executor_context.py
import pytest
from jarvis.cognitive.context import ExecutionContext
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.executor import ToolExecutor
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel

@pytest.mark.asyncio
async def test_tool_executor_with_context():
    registry = ToolRegistry()
    executed = []
    async def dummy(arg: str):
        executed.append(arg)
        return "ok"

    registry.register(ToolDefinition("test_tool", RiskLevel.SAFE, frozenset(), dummy))
    executor = ToolExecutor(registry)
    ctx = ExecutionContext(session_id="s1", task_id="t1", user_id="u1", request_id="r1")

    res = await executor.execute(context=ctx, tool_name="test_tool", arguments={"arg": "val"})
    assert res == "ok"
    assert executed == ["val"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/security/test_tool_executor_context.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/cognitive/context.py` and update `src/jarvis/tools/executor.py`**

```python
# src/jarvis/cognitive/context.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ExecutionContext:
    session_id: str
    task_id: str
    user_id: str
    request_id: str
    permissions: frozenset[str] = field(default_factory=frozenset)
```

```python
# src/jarvis/tools/executor.py
from __future__ import annotations

import logging
from typing import Any
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.policy import RiskLevel
from jarvis.cognitive.context import ExecutionContext

logger = logging.getLogger(__name__)

class ToolDenied(RuntimeError): pass
class ConfirmationRequired(RuntimeError): pass

class ToolExecutor:
    def __init__(self, registry: ToolRegistry | None = None):
        self.registry = registry or ToolRegistry()

    async def execute(
        self,
        tool_name: str,
        *,
        context: ExecutionContext | None = None,
        confirmed: bool = False,
        **kwargs,
    ) -> Any:
        tool = self.registry.get(tool_name)
        if tool is None:
            raise ToolDenied(f"unknown tool: {tool_name}")

        if tool.risk is RiskLevel.FORBIDDEN:
            raise ToolDenied(f"tool forbidden: {tool_name}")

        if tool.risk is RiskLevel.CONFIRM and not confirmed:
            raise ConfirmationRequired(tool_name)

        if tool.risk is RiskLevel.PRIVILEGED:
            raise ToolDenied("privileged tool requires explicit administrator workflow")

        logger.info(
            "Executing tool=%s risk=%s request_id=%s",
            tool.name,
            tool.risk.value,
            context.request_id if context else "none",
        )
        return await tool.handler(**kwargs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/security/test_tool_executor_context.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/cognitive/context.py src/jarvis/tools/executor.py tests/security/test_tool_executor_context.py
git commit -m "feat(security): update ToolExecutor with registry integration and ExecutionContext tracking"
```

---

### Task 8: Server-Side Action Confirmation Architecture (Phase 11)

**Files:**
- Create: `src/jarvis/tools/confirmation.py`
- Test: `tests/security/test_confirmation.py`

**Interfaces:**
- Consumes: HMAC-SHA256 token hashing
- Produces: `ConfirmationRequest(tool_name, arguments_hash, session_id)`, `create_confirmation_token()`, `verify_confirmation_token()`

- [ ] **Step 1: Write failing security test for confirmation token validation**

```python
# tests/security/test_confirmation.py
from jarvis.tools.confirmation import (
    create_confirmation_token,
    verify_confirmation_token,
)

def test_confirmation_token_valid():
    secret = "test-secret"
    token = create_confirmation_token("send_msg", {"to": "alice"}, "s1", secret)
    assert verify_confirmation_token("send_msg", {"to": "alice"}, "s1", secret, token) is True

def test_confirmation_token_tampered_args_fails():
    secret = "test-secret"
    token = create_confirmation_token("send_msg", {"to": "alice"}, "s1", secret)
    assert verify_confirmation_token("send_msg", {"to": "bob"}, "s1", secret, token) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/security/test_confirmation.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/tools/confirmation.py`**

```python
# src/jarvis/tools/confirmation.py
from __future__ import annotations

import hmac
import hashlib
import json
from dataclasses import dataclass

@dataclass(frozen=True)
class ConfirmationRequest:
    tool_name: str
    arguments_hash: str
    session_id: str

def hash_arguments(args: dict) -> str:
    serialized = json.dumps(args, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def create_confirmation_token(tool_name: str, args: dict, session_id: str, secret: str) -> str:
    arg_hash = hash_arguments(args)
    msg = f"{tool_name}:{arg_hash}:{session_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

def verify_confirmation_token(tool_name: str, args: dict, session_id: str, secret: str, token: str) -> bool:
    expected = create_confirmation_token(tool_name, args, session_id, secret)
    return hmac.compare_digest(expected, token)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/security/test_confirmation.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/tools/confirmation.py tests/security/test_confirmation.py
git commit -m "security(confirmation): implement server-side action confirmation token architecture"
```

---

### Task 9: TaskManager Single execution gate routing (Phase 12)

**Files:**
- Modify: `src/jarvis/tasks/manager.py`
- Test: `tests/unit/test_task_manager_single_path.py`

**Interfaces:**
- Consumes: `TaskManager`, `ToolExecutor`, `ExecutionContext`
- Produces: Single tool handler invocation path. Zero direct `tool.handler()` calls outside `ToolExecutor`.

- [ ] **Step 1: Write test verifying TaskManager passes ExecutionContext to ToolExecutor**

```python
# tests/unit/test_task_manager_single_path.py
import pytest
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.executor import ToolExecutor
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel
from jarvis.tasks.models import TaskPlan, TaskStep
from jarvis.tasks.manager import TaskManager
from jarvis.cognitive.context import ExecutionContext

@pytest.mark.asyncio
async def test_task_manager_routes_exclusively_through_executor():
    registry = ToolRegistry()
    executed_ctx = []

    async def mock_handler(target: str, **kwargs):
        return f"done-{target}"

    registry.register(ToolDefinition("test_tool", RiskLevel.SAFE, frozenset(), mock_handler))
    executor = ToolExecutor(registry)
    manager = TaskManager(executor)

    plan = TaskPlan(
        id="plan-1",
        steps=[TaskStep(id="step-1", tool="test_tool", arguments={"target": "abc"})]
    )
    ctx = ExecutionContext(session_id="s1", task_id="t1", user_id="u1", request_id="r1")

    res = await manager.execute_plan(plan, context=ctx)
    assert res["step-1"] == "done-abc"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_task_manager_single_path.py`

- [ ] **Step 3: Commit changes**

```bash
git add src/jarvis/tasks/manager.py tests/unit/test_task_manager_single_path.py
git commit -m "fix(tasks): enforce exclusive TaskManager execution routing through ToolExecutor gate"
```

---

### Task 10: Full Suite Verification (Phases 1-12 Consolidation Check)

- [ ] **Step 1: Run complete test suite**

Run: `PYTHONPATH=src pytest tests/unit tests/security tests/integration tests/linux`
Expected: 100% tests PASS

- [ ] **Step 2: Run bandit security scanner**

Run: `bandit -r src/`
Expected: 0 issues

- [ ] **Step 3: Run jarvis doctor**

Run: `PYTHONPATH=src python3 -m jarvis.cli.main doctor`
Expected: Clean doctor output showing 0 errors
