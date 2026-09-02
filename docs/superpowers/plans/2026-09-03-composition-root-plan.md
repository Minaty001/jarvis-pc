# JARVIS-PC Composition Root & Runtime Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a proper composition root in `Application` that owns the entire object graph (`Settings → ToolRegistry → ToolExecutor → TaskManager → API`), fix CLI `run` to keep the process alive with signal handling, make `ExecutionContext` mandatory, remove default confirmation secret, add token expiry, remove arbitrary shell tool, use async rate limiter, enforce request size limits, and fix `jarvis status`.

---

## Task 1: Composition Root — Application owns the full object graph (P0 CRITICAL)

**Fixes issues:** #5 (empty executor), #7 (registry not wired), #19 (Application isn't composition root)

**Files to create/modify:**
- Create: `src/jarvis/tools/builtin/registry_init.py` — single function that registers ALL safe builtin tools
- Modify: `src/jarvis/app/application.py` — own registry, executor, task_manager, planner, api
- Modify: `src/jarvis/api/app.py` — accept executor via dependency injection, remove module-level `_tool_executor = ToolExecutor()`
- Modify: `task_engine/manager.py` — accept `ToolExecutor` via constructor injection, kill `_default_step_runner`
- Test: `tests/unit/test_composition_root.py`

**Constraints:**
- `ToolExecutor()` MUST NOT appear anywhere except `Application.__init__` or factory method.
- `ToolRegistry()` MUST NOT appear anywhere except `Application.__init__` or factory method.
- `task_engine.manager.TaskManager()` singleton at module level MUST be removed; TaskManager is created by Application.

- [ ] **Step 1: Write test**

Create `tests/unit/test_composition_root.py`:
```python
"""Verify Application is the single composition root for the full object graph."""
import ast
import pytest
from pathlib import Path

def test_no_standalone_executor_construction():
    """No file outside Application may construct ToolExecutor()."""
    src = Path("src/jarvis")
    violations = []
    for py in src.rglob("*.py"):
        if "test" in str(py) or "__pycache__" in str(py):
            continue
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name == "ToolExecutor" and "application.py" not in str(py):
                    violations.append(f"{py.relative_to(src)}:{node.lineno}")
    assert not violations, f"ToolExecutor() constructed outside Application: {violations}"

def test_no_standalone_registry_construction():
    """No file outside Application may construct ToolRegistry()."""
    src = Path("src/jarvis")
    violations = []
    for py in src.rglob("*.py"):
        if "test" in str(py) or "__pycache__" in str(py):
            continue
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name == "ToolRegistry" and "application.py" not in str(py):
                    violations.append(f"{py.relative_to(src)}:{node.lineno}")
    assert not violations, f"ToolRegistry() constructed outside Application: {violations}"

def test_application_creates_full_graph():
    from jarvis.app.application import Application
    app = Application()
    assert app.registry is not None
    assert app.executor is not None
    assert app.executor.registry is app.registry
    assert len(app.registry.list()) > 0, "Registry must have tools registered"

def test_task_manager_uses_injected_executor():
    """task_engine.manager.TaskManager must accept executor, not create its own."""
    src = Path("task_engine/manager.py")
    content = src.read_text()
    assert "ToolExecutor()" not in content, "TaskManager must not construct ToolExecutor()"
```

- [ ] **Step 2: Create `src/jarvis/tools/builtin/registry_init.py`**

Single function `register_all_builtins(registry)` that registers:
- `read_file` (SAFE, capabilities={"filesystem.read"})
- `write_file` (CONFIRM, capabilities={"filesystem.write"})
- `open_application` (CONFIRM, capabilities={"desktop.applications"})
- `find_processes` (SAFE, capabilities={"system.read"})
- `check_camera` (SAFE, capabilities={"media.camera"})
- `take_photo` (CONFIRM, capabilities={"media.camera"})
- `web_search` (SAFE, capabilities={"network.read"})
- `system_info` (SAFE, capabilities={"system.read"})

No `run_command` / arbitrary shell tool.

- [ ] **Step 3: Rewrite `src/jarvis/app/application.py`**

```python
class Application:
    def __init__(self, *, settings=None):
        from jarvis.config.settings import get_settings
        from jarvis.tools.registry import ToolRegistry
        from jarvis.tools.executor import ToolExecutor
        from jarvis.tools.builtin.registry_init import register_all_builtins

        self.settings = settings or get_settings()
        self.registry = ToolRegistry()
        register_all_builtins(self.registry)
        self.executor = ToolExecutor(
            registry=self.registry,
            confirmation_secret=self.settings.confirmation_secret,
        )
        # Further components receive executor:
        self.task_manager = None  # Assigned during start()
        self.api = None
        self.voice = None
        self._started = False
        self._stop_event = None
```

- [ ] **Step 4: Modify `src/jarvis/api/app.py`**

Remove `_tool_executor = ToolExecutor()` module-level singleton.
Add `create_api_app(executor: ToolExecutor) -> FastAPI` factory function.
The `/execute` endpoint must create an `ExecutionContext` from request metadata.

- [ ] **Step 5: Modify `task_engine/manager.py`**

- Remove `_default_step_runner` function entirely.
- `TaskManager.__init__` accepts `tool_executor: ToolExecutor`.
- `DAGExecutor` step runner uses `self._tool_executor.execute(...)`.
- Remove module-level `task_manager = TaskManager()` singleton.

- [ ] **Step 6: Run tests**

```bash
PYTHONPATH=src pytest tests/unit/test_composition_root.py tests/architecture/
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor(core): build Application composition root owning full ToolRegistry→ToolExecutor→TaskManager object graph"
```

---

## Task 2: CLI `run` persistent lifecycle with signal handling (P0 CRITICAL)

**Fixes issues:** #20 (CLI run exits immediately)

**Files to modify:**
- Modify: `src/jarvis/cli/main.py`
- Modify: `src/jarvis/app/application.py` (add `run_until_stopped` or signal wait)
- Test: `tests/unit/test_cli_lifecycle.py`

- [ ] **Step 1: Write test**

```python
import asyncio
import signal
import pytest
from jarvis.app.application import Application

@pytest.mark.asyncio
async def test_application_run_until_stopped():
    app = Application()
    task = asyncio.create_task(app.run_until_stopped())
    await asyncio.sleep(0.1)
    assert app.is_started
    app.request_stop()
    await task
    assert not app.is_started
```

- [ ] **Step 2: Add `run_until_stopped()` to Application**

```python
async def run_until_stopped(self):
    await self.start()
    self._stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, self._stop_event.set)
    await self._stop_event.wait()
    await self.stop()

def request_stop(self):
    if self._stop_event:
        self._stop_event.set()
```

- [ ] **Step 3: Update `run_cli` to call `asyncio.run(app.run_until_stopped())`**

- [ ] **Step 4: Run tests & commit**

```bash
git commit -m "fix(cli): keep jarvis run alive with signal-based graceful shutdown"
```

---

## Task 3: Make ExecutionContext mandatory & fix API context creation (P0 HIGH)

**Fixes issues:** #9 (capability check bypassable when context=None)

**Files to modify:**
- Modify: `src/jarvis/tools/executor.py` — change `context: Optional[ExecutionContext]` to `context: ExecutionContext`
- Modify: `src/jarvis/api/app.py` — create `ExecutionContext` for every `/execute` request
- Modify: `src/jarvis/tasks/manager.py` — require context in execute_step
- Test: `tests/security/test_context_mandatory.py`

- [ ] **Step 1: Write test**

```python
@pytest.mark.asyncio
async def test_executor_rejects_missing_context():
    executor = ToolExecutor(registry)
    with pytest.raises(TypeError):
        await executor.execute("tool", arguments={})
```

- [ ] **Step 2: Make context mandatory in ToolExecutor.execute()**

- [ ] **Step 3: Update API to create ExecutionContext per request**

```python
import uuid
ctx = ExecutionContext(
    session_id=request.headers.get("X-Session-Id", "api"),
    task_id=f"api-{uuid.uuid4().hex[:8]}",
    user_id="api-user",
    request_id=str(uuid.uuid4()),
    permissions=frozenset(["filesystem.read", "system.read", "network.read"]),
)
```

- [ ] **Step 4: Run tests & commit**

```bash
git commit -m "security(executor): make ExecutionContext mandatory, reject unauthenticated tool execution"
```

---

## Task 4: Remove default confirmation secret & add token expiry (P0 HIGH)

**Fixes issues:** #10 (dangerous fallback secret), #11 (no token expiry)

**Files to modify:**
- Modify: `src/jarvis/tools/executor.py` — remove `"jarvis-default-secret"` fallback, fail closed
- Modify: `src/jarvis/tools/confirmation.py` — add `issued_at`, `expires_at`, `nonce` to token payload
- Modify: `src/jarvis/config/settings.py` — add `confirmation_secret` setting
- Test: `tests/security/test_confirmation_expiry.py`

- [ ] **Step 1: Write test**

```python
def test_missing_secret_fails_closed():
    """Executor must raise ConfigurationError if no secret is configured."""

def test_expired_token_rejected():
    """Token created >5min ago must be rejected."""

def test_token_contains_nonce():
    """Each token must have unique nonce preventing replay."""
```

- [ ] **Step 2: Update confirmation.py token format**

Token payload: `version:1|tool:{name}|args_hash:{hash}|session:{sid}|nonce:{uuid4}|issued:{timestamp}|expires:{timestamp+300}`
HMAC signs the full payload string.
`verify_confirmation_token` checks expiry before HMAC comparison.

- [ ] **Step 3: Remove default secret from executor, use settings**

```python
if not self._confirmation_secret:
    raise ConfigurationError("JARVIS_CONFIRMATION_SECRET is not configured")
```

- [ ] **Step 4: Run tests & commit**

```bash
git commit -m "security(confirmation): add token expiry/nonce, remove dangerous default secret, fail closed"
```

---

## Task 5: Remove arbitrary shell tool entirely (P0 CRITICAL)

**Fixes issues:** #12 (arbitrary command still accessible)

**Files to modify:**
- Remove: `tools/builtin/shell_exec.py`
- Modify: `tools/__init__.py` — remove `run_command` references
- Test: `tests/security/test_no_arbitrary_shell.py`

- [ ] **Step 1: Write test**

```python
def test_shell_exec_file_does_not_exist():
    assert not Path("tools/builtin/shell_exec.py").exists()

def test_no_run_command_registration():
    """No tool named 'run_command' exists in the registry."""
    from jarvis.app.application import Application
    app = Application()
    assert not app.registry.has("run_command")
```

- [ ] **Step 2: Delete `tools/builtin/shell_exec.py`**

- [ ] **Step 3: Run tests & commit**

```bash
git rm tools/builtin/shell_exec.py && git commit -m "security(tools): remove arbitrary shell execution tool entirely"
```

---

## Task 6: Use async rate limiter & enforce request body size (P1 MEDIUM)

**Fixes issues:** #16 (sync check instead of async), #17 (no request size enforcement)

**Files to modify:**
- Modify: `src/jarvis/tools/executor.py` — `await self.rate_limiter.check_async(...)` instead of `self.rate_limiter.check(...)`
- Modify: `src/jarvis/api/app.py` — add Content-Length middleware returning 413
- Test: `tests/security/test_rate_limit_and_body_size.py`

- [ ] **Step 1: Write test**

- [ ] **Step 2: Switch executor to `check_async` — make `execute()` use `await self.rate_limiter.check_async(target_name)`**

- [ ] **Step 3: Add request body size middleware**

```python
@app.middleware("http")
async def limit_request_body(request, call_next):
    cl = request.headers.get("content-length")
    if cl and int(cl) > settings.max_request_bytes:
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})
    return await call_next(request)
```

- [ ] **Step 4: Run tests & commit**

```bash
git commit -m "security(api): use async rate limiter and enforce HTTP request body size limits"
```

---

## Task 7: Fix `jarvis status` to check real service state (P1)

**Fixes issues:** #21 (fake status)

**Files to modify:**
- Modify: `src/jarvis/cli/main.py` — `jarvis status` checks systemd + health endpoint + PID
- Test: `tests/unit/test_cli_status.py`

- [ ] **Step 1: Write test**

```python
def test_status_checks_systemd(monkeypatch):
    """jarvis status must not hardcode 'operational'."""
    from jarvis.cli.main import check_status
    # Mock subprocess for systemctl
    result = check_status()
    assert result in ("running", "stopped", "unknown")
```

- [ ] **Step 2: Implement `check_status()`**

Check `systemctl --user is-active jarvis.service`, then try `GET http://127.0.0.1:8000/health`, then check PID file.

- [ ] **Step 3: Run tests & commit**

```bash
git commit -m "fix(cli): replace fake jarvis status with real systemd/health/PID checks"
```

---

## Task 8: Full Verification

- [ ] **Step 1: Full test suite:** `PYTHONPATH=src pytest tests/unit tests/security tests/integration tests/linux tests/architecture`
- [ ] **Step 2: Bandit:** `bandit -r src/`
- [ ] **Step 3: Doctor:** `PYTHONPATH=src python3 -m jarvis.cli.main doctor`
- [ ] **Step 4: Push**
