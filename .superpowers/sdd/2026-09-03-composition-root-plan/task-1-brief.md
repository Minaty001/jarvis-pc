# Task 1 Brief: Composition Root — Application owns the full object graph

**Fixes issues:** #5 (empty executor per execution), #7 (registry not wired), #19 (Application isn't composition root)

**This is the most critical task. Read every instruction carefully.**

## Problem

Current code has `ToolExecutor()` constructed inline in `task_engine/manager.py:_default_step_runner`, which creates a brand-new empty `ToolRegistry()` every call. The API also has a module-level `_tool_executor = ToolExecutor()` with no tools registered. The result: tools pass through the security gate, but the gate has no registered tools so nothing works.

## Target Architecture

```
Application.__init__()
    ├── settings = get_settings()
    ├── registry = ToolRegistry()
    ├── register_all_builtins(registry)
    ├── executor = ToolExecutor(registry)
    └── (task_manager, api created during start())
```

## Files to create/modify

### 1. CREATE `src/jarvis/tools/builtin/registry_init.py`

```python
"""Single function that populates a ToolRegistry with all builtin tools."""
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel
from jarvis.tools.registry import ToolRegistry


def register_all_builtins(registry: ToolRegistry) -> None:
    """Register every builtin tool into the given registry."""
    from jarvis.tools.builtin.filesystem import SafeFileStore
    from jarvis.tools.builtin.applications import open_application
    from jarvis.tools.builtin.processes import find_processes
    from jarvis.tools.builtin.media import check_camera_permissions
    from jarvis.system.paths import xdg_data_home
    from pathlib import Path

    # Create a default file store rooted at user home
    _store = SafeFileStore(Path.home())

    registry.register(ToolDefinition(
        name="read_file",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"filesystem.read"}),
        handler=_store.read_text,
    ))
    registry.register(ToolDefinition(
        name="write_file",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"filesystem.write"}),
        handler=_store.write_text,
    ))
    registry.register(ToolDefinition(
        name="open_application",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"desktop.applications"}),
        handler=open_application,
    ))
    registry.register(ToolDefinition(
        name="find_processes",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"system.read"}),
        handler=find_processes,
    ))
    registry.register(ToolDefinition(
        name="check_camera",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"media.camera"}),
        handler=check_camera_permissions,
    ))
```

### 2. REWRITE `src/jarvis/app/application.py`

Application must:
- Create `ToolRegistry` in `__init__`
- Call `register_all_builtins(registry)` in `__init__`
- Create `ToolExecutor(registry=registry)` in `__init__`
- Expose `self.registry` and `self.executor` as public attributes
- Keep startup rollback logic
- Keep `start()` and `stop()` methods

```python
from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

logger = logging.getLogger(__name__)


class Application:
    """Central Application lifecycle manager and composition root for JARVIS-PC."""

    def __init__(self, *, settings=None) -> None:
        from jarvis.tools.registry import ToolRegistry
        from jarvis.tools.executor import ToolExecutor
        from jarvis.tools.builtin.registry_init import register_all_builtins

        if settings is None:
            from jarvis.config.settings import get_settings
            settings = get_settings()

        self.settings = settings
        self.registry = ToolRegistry()
        register_all_builtins(self.registry)
        self.executor = ToolExecutor(registry=self.registry)

        self.voice: Any = None
        self.scheduler: Any = None
        self.api: Any = None

        self._started: bool = False
        self._stopping: bool = False
        self._stop_event: asyncio.Event | None = None

    @property
    def is_started(self) -> bool:
        return self._started

    async def start(self) -> None:
        if self._started:
            return

        logger.info("Starting JARVIS application")
        components = [self.scheduler, self.voice, self.api]
        started_components: list[Any] = []

        try:
            for component in components:
                if component is not None and hasattr(component, "start") and callable(component.start):
                    await component.start()
                    started_components.append(component)
        except Exception:
            logger.exception("Application startup failed; rolling back started components")
            for component in reversed(started_components):
                if hasattr(component, "stop") and callable(component.stop):
                    try:
                        await component.stop()
                    except Exception as stop_exc:
                        logger.exception("Failed stopping component during rollback: %r", stop_exc)
            raise

        self._started = True
        logger.info("JARVIS started successfully (%d tools registered)", len(self.registry.list()))

    async def stop(self) -> None:
        if not self._started or self._stopping:
            return

        self._stopping = True
        logger.info("Stopping JARVIS application")
        errors: list[Exception] = []

        for component in (self.api, self.voice, self.scheduler):
            if component is None:
                continue
            if hasattr(component, "stop") and callable(component.stop):
                try:
                    await component.stop()
                except Exception as exc:
                    logger.exception("Failed stopping %r", component)
                    errors.append(exc)

        self._started = False
        self._stopping = False

        if errors:
            raise RuntimeError(f"{len(errors)} component(s) failed to stop")

    async def run_until_stopped(self) -> None:
        """Start application and block until stop signal received."""
        await self.start()
        self._stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._stop_event.set)
        logger.info("JARVIS running. Press Ctrl+C to stop.")
        await self._stop_event.wait()
        await self.stop()

    def request_stop(self) -> None:
        """Programmatically request graceful shutdown."""
        if self._stop_event:
            self._stop_event.set()
```

### 3. MODIFY `src/jarvis/api/app.py`

Remove the module-level `_tool_executor = ToolExecutor()`.
Add a `create_api_app(executor: ToolExecutor) -> FastAPI` factory function.
The executor is passed via closure, NOT constructed inside the module.

```python
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from jarvis.api.auth import verify_auth
from jarvis.api.schemas import ExecuteRequest, ExecuteResponse
from jarvis.tools.executor import ConfirmationRequired, ToolDenied, ToolExecutor
from jarvis.tools.rate_limit import RateLimitExceeded
from jarvis.cognitive.context import ExecutionContext

import uuid


def create_api_app(executor: ToolExecutor) -> FastAPI:
    """Factory: create FastAPI app with injected executor."""
    api = FastAPI(title="JARVIS API", version="1.0.0")

    @api.exception_handler(ToolDenied)
    async def tool_denied_handler(request: Request, exc: ToolDenied):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    @api.exception_handler(ConfirmationRequired)
    async def confirmation_required_handler(request: Request, exc: ConfirmationRequired):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @api.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": str(exc)})

    @api.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})

    @api.get("/health")
    async def health():
        return {"status": "ok"}

    @api.post("/execute", response_model=ExecuteResponse)
    async def execute(request: ExecuteRequest, _: None = Depends(verify_auth)):
        ctx = ExecutionContext(
            session_id="api",
            task_id=f"api-{uuid.uuid4().hex[:8]}",
            user_id="api-user",
            request_id=str(uuid.uuid4()),
            permissions=frozenset({"filesystem.read", "system.read", "network.read"}),
        )
        try:
            result = await executor.execute(
                request.tool,
                context=ctx,
                confirmation_token=request.confirmation_token,
                arguments=request.arguments,
            )
            return ExecuteResponse(ok=True, result=result)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown tool: {request.tool}") from exc

    return api


# Backward-compatible module-level app for tests that import `from jarvis.api.app import app`
# This uses an empty executor — real runtime should use create_api_app()
app = create_api_app(ToolExecutor())
```

IMPORTANT: Keep the backward-compatible `app = create_api_app(ToolExecutor())` at module level ONLY so existing test imports don't break. But the AST test should verify that no PRODUCTION code calls `ToolExecutor()` outside `application.py`. The test should exclude `app.py` since it has the backward-compat shim clearly documented.

### 4. MODIFY `task_engine/manager.py`

- Delete the `_default_step_runner` function entirely.
- Make `TaskManager.__init__` accept `tool_executor: ToolExecutor | None = None`.
- Store it as `self._tool_executor`.
- Create a bound step runner method `_step_runner` that uses `self._tool_executor.execute(...)`.
- In `run_now()`, pass `self._step_runner` to `DAGExecutor`.
- Remove the module-level `task_manager = TaskManager()` singleton.

Key change in `__init__`:
```python
def __init__(self, tool_executor=None):
    self._tool_executor = tool_executor
    ...existing fields...
```

Key change — new bound method:
```python
async def _step_runner(self, action: str, params: dict, context=None):
    """Dispatches through the injected ToolExecutor."""
    if self._tool_executor is None:
        return ActionResult.fail("No ToolExecutor configured")
    try:
        res = await self._tool_executor.execute(action, context=context, arguments=params)
        return ActionResult.ok(str(res))
    except Exception as e:
        return ActionResult.fail(str(e))
```

In `run_now`, change line 142:
```python
executor = DAGExecutor(step_runner=self._step_runner, max_parallel=task.policy.max_parallel_steps)
```

Remove the last line `task_manager = TaskManager()`.

### 5. WRITE TESTS `tests/unit/test_composition_root.py`

```python
"""Verify Application is the single composition root for the full object graph."""
import ast
import pytest
from pathlib import Path


def test_no_standalone_executor_construction():
    """No src/jarvis file outside application.py and app.py may construct ToolExecutor()."""
    src = Path("src/jarvis")
    # app.py has a backward-compat shim, allow it
    allowed = {"application.py", "app.py"}
    violations = []
    for py in src.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        if py.name in allowed:
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
                if name == "ToolExecutor":
                    violations.append(f"{py.relative_to(src)}:{node.lineno}")
    assert not violations, f"ToolExecutor() constructed outside Application: {violations}"


def test_application_creates_full_graph():
    from jarvis.app.application import Application
    app = Application()
    assert app.registry is not None
    assert app.executor is not None
    assert app.executor.registry is app.registry
    assert len(app.registry.list()) > 0, "Registry must have tools registered"


def test_task_manager_no_inline_executor():
    """task_engine.manager.TaskManager must not construct ToolExecutor() inline."""
    src = Path("task_engine/manager.py")
    content = src.read_text()
    assert "ToolExecutor()" not in content, "TaskManager must not construct ToolExecutor()"
```

## Execution steps

1. Write test file `tests/unit/test_composition_root.py`
2. Run test — confirm failures: `PYTHONPATH=src pytest tests/unit/test_composition_root.py`
3. Create `src/jarvis/tools/builtin/registry_init.py`
4. Rewrite `src/jarvis/app/application.py`
5. Rewrite `src/jarvis/api/app.py`
6. Modify `task_engine/manager.py`
7. Run test — confirm passes: `PYTHONPATH=src pytest tests/unit/test_composition_root.py`
8. Run broader suites to catch regressions: `PYTHONPATH=src pytest tests/unit tests/security tests/integration tests/architecture`
9. Fix any test failures from the refactor (update tests that construct `ToolExecutor()` directly — those are fine in tests)
10. Commit: `git add -A && git commit -m "refactor(core): build Application composition root owning full ToolRegistry→ToolExecutor→TaskManager object graph"`

## Report

Save report to `/home/shanu/Desktop/jarvis-pc/.superpowers/sdd/2026-09-03-composition-root-plan/task-1-report.md`.
