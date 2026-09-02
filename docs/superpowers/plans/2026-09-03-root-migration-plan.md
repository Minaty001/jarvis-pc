# JARVIS-PC Root Migration & Execution Gate Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completely eliminate legacy execution bypasses, consolidate dual registries/executors, remove arbitrary shell and camera sudo escalation, wire HMAC confirmation tokens and capability checks into `ToolExecutor`, and make `src/jarvis/app/application.py` the sole authoritative application lifecycle manager.

**Architecture:** Session/Context -> Orchestrator -> Planner -> TaskManager -> ToolExecutor (Single Execution Gate) -> Capability & Token Verification -> Single ToolRegistry -> Safe Tools.

---

### Task 1: Eliminate TaskManager Direct Handler Bypass & Unify Task Engines (P0)

**Files to touch:**
- Modify: `task_engine/manager.py`
- Modify: `src/jarvis/tasks/manager.py`
- Test: `tests/architecture/test_handler_invocation_audit.py`
- Test: `tests/unit/test_task_manager_single_path.py`

- [ ] **Step 1: Write test verifying TaskManager routes step execution strictly through ToolExecutor**

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
    executed_args = []

    async def mock_handler(target: str, **kwargs):
        executed_args.append(target)
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
    assert executed_args == ["abc"]
```

- [ ] **Step 2: Modify `task_engine/manager.py` and `src/jarvis/tasks/manager.py`**

Replace `_default_step_runner` in `task_engine/manager.py`:
```python
async def _default_step_runner(action: str, params: dict, context=None) -> ActionResult:
    """Dispatches exclusively through ToolExecutor."""
    try:
        from jarvis.tools.executor import ToolExecutor
        from jarvis.tools.registry import ToolRegistry
        # Route through ToolExecutor
        executor = ToolExecutor()
        res = await executor.execute(action, context=context, **params)
        return ActionResult.ok(str(res))
    except Exception as e:
        return ActionResult.fail(str(e))
```

- [ ] **Step 3: Run architectural audit test**

Run: `PYTHONPATH=src pytest tests/architecture/test_handler_invocation_audit.py`
Expected: PASS (0 direct `.handler(` calls outside `ToolExecutor`).

- [ ] **Step 4: Commit changes**

```bash
git add task_engine/manager.py src/jarvis/tasks/manager.py tests/unit/test_task_manager_single_path.py tests/architecture/test_handler_invocation_audit.py
git commit -m "security(tasks): eliminate direct tool handler bypass in task_engine and enforce single ToolExecutor gate"
```

---

### Task 2: Remove Arbitrary Shell Tool & Camera Sudo Escalation (P0)

**Files to touch:**
- Remove/Modify: `tools/builtin/shell_exec.py`
- Modify: `tools/builtin/camera.py`
- Modify: `src/jarvis/tools/builtin/media.py`
- Test: `tests/security/test_no_shell_or_sudo.py`

- [ ] **Step 1: Write security audit test verifying zero shell=True and zero sudo calls**

```python
# tests/security/test_no_shell_or_sudo.py
from pathlib import Path

def test_no_shell_exec_tool():
    shell_tool = Path("tools/builtin/shell_exec.py")
    if shell_tool.exists():
        content = shell_tool.read_text()
        assert "shell=True" not in content

def test_no_sudo_in_camera_tools():
    camera_tool = Path("tools/builtin/camera.py")
    if camera_tool.exists():
        assert "sudo" not in camera_tool.read_text()
    media_tool = Path("src/jarvis/tools/builtin/media.py")
    assert "sudo" not in media_tool.read_text()
```

- [ ] **Step 2: Remove `shell=True` from `tools/builtin/shell_exec.py` and `sudo` from `tools/builtin/camera.py`**

Remove the `sudo usermod` subprocess call in `tools/builtin/camera.py`.
Replace `shell_exec.py` raw subprocess execution with safe `run_process` argument list execution or deprecate tool.

- [ ] **Step 3: Run security tests**

Run: `PYTHONPATH=src pytest tests/security/test_no_shell_or_sudo.py`

- [ ] **Step 4: Commit changes**

```bash
git add tools/builtin/camera.py tools/builtin/shell_exec.py src/jarvis/tools/builtin/media.py tests/security/test_no_shell_or_sudo.py
git commit -m "security(tools): remove arbitrary shell command execution and runtime camera sudo usermod escalation"
```

---

### Task 3: Wire HMAC Confirmation Tokens & Capability Authorization into ToolExecutor (P0)

**Files to touch:**
- Modify: `src/jarvis/tools/executor.py`
- Modify: `src/jarvis/api/app.py`
- Modify: `src/jarvis/api/schemas.py`
- Test: `tests/security/test_tool_executor_confirmation_and_capabilities.py`

- [ ] **Step 1: Write security tests for token verification and capability checking in ToolExecutor**

```python
# tests/security/test_tool_executor_confirmation_and_capabilities.py
import pytest
from jarvis.tools.executor import ToolExecutor, ToolDenied, ConfirmationRequired
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel
from jarvis.cognitive.context import ExecutionContext
from jarvis.tools.confirmation import create_confirmation_token

@pytest.mark.asyncio
async def test_capability_authorization_enforced():
    registry = ToolRegistry()
    async def dummy(): return "ok"
    registry.register(ToolDefinition("write_file", RiskLevel.SAFE, frozenset(["filesystem.write"]), dummy))
    executor = ToolExecutor(registry)

    # Context missing filesystem.write capability
    ctx = ExecutionContext("s1", "t1", "u1", "r1", permissions=frozenset(["filesystem.read"]))
    with pytest.raises(ToolDenied, match="Insufficient capabilities"):
        await executor.execute("write_file", context=ctx)

@pytest.mark.asyncio
async def test_confirmation_token_required_for_confirm_risk():
    registry = ToolRegistry()
    async def dummy(): return "ok"
    registry.register(ToolDefinition("send_msg", RiskLevel.CONFIRM, frozenset(), dummy))
    executor = ToolExecutor(registry)
    ctx = ExecutionContext("s1", "t1", "u1", "r1")

    # Missing token -> ConfirmationRequired
    with pytest.raises(ConfirmationRequired):
        await executor.execute("send_msg", context=ctx, arguments={"to": "alice"})

    # Valid token -> Success
    secret = "secret-key"
    token = create_confirmation_token("send_msg", {"to": "alice"}, "s1", secret)
    res = await executor.execute("send_msg", context=ctx, confirmation_token=token, secret=secret, arguments={"to": "alice"})
    assert res == "ok"
```

- [ ] **Step 2: Update `ToolExecutor.execute()` in `src/jarvis/tools/executor.py`**

1. Capability Check:
```python
if context and tool.capabilities:
    if not (tool.capabilities <= context.permissions):
        raise ToolDenied(f"Insufficient capabilities for tool '{tool.name}'. Required: {set(tool.capabilities)}")
```
2. Confirmation Token Verification:
```python
if tool.risk is RiskLevel.CONFIRM:
    if not confirmation_token:
        raise ConfirmationRequired(tool.name)
    session_id = context.session_id if context else ""
    if not verify_confirmation_token(tool.name, arguments, session_id, secret or "jarvis-default-secret", confirmation_token):
        raise ToolDenied("Invalid or tampered confirmation token")
```

- [ ] **Step 3: Update FastAPI `/execute` endpoint in `src/jarvis/api/app.py` & schemas**

Add `confirmation_token: Optional[str] = None` to `ExecuteRequest` schema and pass to `executor.execute()`.

- [ ] **Step 4: Run security tests**

Run: `PYTHONPATH=src pytest tests/security/test_tool_executor_confirmation_and_capabilities.py`

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/tools/executor.py src/jarvis/api/app.py src/jarvis/api/schemas.py tests/security/test_tool_executor_confirmation_and_capabilities.py
git commit -m "security(executor): enforce capability authorization and wire HMAC confirmation token verification into ToolExecutor gate"
```

---

### Task 4: Consolidate Registries & Execators & Migrate `run.py` to `Application` (P0)

**Files to touch:**
- Remove: `tools/executor.py`
- Remove: `tools/registry.py`
- Modify: `run.py`
- Modify: `src/jarvis/cli/main.py`
- Test: `tests/integration/test_run_entrypoint.py`

- [ ] **Step 1: Replace legacy imports in `run.py` with `src/jarvis` imports**

Update `run.py` to import `from jarvis.tools.registry import ToolRegistry` and `from jarvis.app.application import Application`.
Delegate `main()` in `run.py` to launch `jarvis.cli.main.run_cli()`.

- [ ] **Step 2: Update `src/jarvis/cli/main.py` to launch `Application.start()` for `jarvis run`**

```python
# In src/jarvis/cli/main.py:
import asyncio
from jarvis.app.application import Application

def run_cli(args: list[str] | None = None) -> None:
    if args is None:
        args = sys.argv[1:]

    cmd = args[0] if args else "run"
    if cmd == "run":
        app = Application()
        asyncio.run(app.start())
```

- [ ] **Step 3: Delete legacy duplicate registry and executor root files (`tools/executor.py`, `tools/registry.py`)**

- [ ] **Step 4: Run full test suite**

Run: `PYTHONPATH=src pytest tests/unit tests/security tests/integration tests/linux tests/architecture`

- [ ] **Step 5: Commit changes**

```bash
git add run.py src/jarvis/cli/main.py tests/integration/test_run_entrypoint.py
git rm -f tools/executor.py tools/registry.py || true
git commit -m "refactor(core): consolidate duplicate registries/executors and make src/jarvis Application authoritative"
```

---

### Task 5: Harden Audit Redaction, Concurrency-Safe Rate Limiting & Bounded Process Output (P2)

**Files to touch:**
- Modify: `src/jarvis/tools/audit.py`
- Modify: `src/jarvis/tools/rate_limit.py`
- Modify: `src/jarvis/system/process.py`
- Modify: `src/jarvis/app/application.py`
- Test: `tests/security/test_hardened_security.py`

- [ ] **Step 1: Write test for regex secret pattern redaction, thread-safe rate limiter, and startup rollback**

- [ ] **Step 2: Update `src/jarvis/tools/audit.py` with regex secret pattern matching (`sk-[a-zA-Z0-9]+`, `eyJ[a-zA-Z0-9_-]+`)**

- [ ] **Step 3: Update `src/jarvis/tools/rate_limit.py` with `asyncio.Lock()`**

- [ ] **Step 4: Update `src/jarvis/system/process.py` with stdout/stderr byte limits**

- [ ] **Step 5: Update `src/jarvis/app/application.py` with startup rollback on subsystem failure**

- [ ] **Step 6: Commit changes**

```bash
git add src/jarvis/tools/audit.py src/jarvis/tools/rate_limit.py src/jarvis/system/process.py src/jarvis/app/application.py tests/security/test_hardened_security.py
git commit -m "security(hardening): add regex secret pattern redaction, asyncio.Lock rate limiting, bounded process output, and startup rollback"
```

---

### Task 6: Real Doctor, Systemd Unit & Installer Fixes (P1)

**Files to touch:**
- Modify: `src/jarvis/cli/doctor.py`
- Modify: `deploy/systemd/jarvis.service`
- Modify: `scripts/install.sh`
- Test: `tests/linux/test_installer_and_doctor.py`

- [ ] **Step 1: Enhance `src/jarvis/cli/doctor.py` to perform empirical read/write checks on XDG directories and dependency imports**
- [ ] **Step 2: Update `deploy/systemd/jarvis.service` removing `User=%u` and setting `ExecStart=%h/.local/share/jarvis/venv/bin/jarvis run`**
- [ ] **Step 3: Update `scripts/install.sh` with `set -Eeuo pipefail` and full venv/package installation steps**
- [ ] **Step 4: Commit changes**

```bash
git add src/jarvis/cli/doctor.py deploy/systemd/jarvis.service scripts/install.sh tests/linux/test_installer_and_doctor.py
git commit -m "fix(deploy): repair systemd user service unit, installer script, and real Doctor empirical checks"
```

---

### Task 7: Full Verification Suite & Final Cleanup

- [ ] **Step 1: Run complete test suite**

Run: `PYTHONPATH=src pytest tests/unit tests/security tests/integration tests/linux tests/architecture`

- [ ] **Step 2: Run bandit security scan**

Run: `bandit -r src/`

- [ ] **Step 3: Run jarvis doctor**

Run: `PYTHONPATH=src python3 -m jarvis.cli.main doctor`

- [ ] **Step 4: Push to origin**
