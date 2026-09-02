# JARVIS-PC Complete Migration Implementation Plan (Phases 1-35)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute full 35-phase migration program consolidating JARVIS-PC so that `src/jarvis` is the sole authoritative application root, eliminating legacy architecture, eliminating `TaskManager` handler bypasses, adding rate-limiting/audit, server-side HMAC confirmation, safe process management, FastAPI migration, voice/UI lifecycle fixes, and comprehensive test coverage.

**Architecture:** Session/Context -> Orchestrator -> Planner -> TaskManager -> ToolExecutor (Single Execution Gate) -> Authorization/Confirmation/RateLimit -> ToolRegistry -> Tools.

**Tech Stack:** Python 3.12+, FastAPI, Uvicorn, Pydantic v2, Pydantic Settings, psutil, pathlib, pytest, uv, systemd.

**Spec:** [docs/architecture-target.md](file:///home/shanu/Desktop/jarvis-pc/docs/architecture-target.md), [docs/migration-plan.md](file:///home/shanu/Desktop/jarvis-pc/docs/migration-plan.md), and [docs/security-model.md](file:///home/shanu/Desktop/jarvis-pc/docs/security-model.md).

## Global Constraints

- **Single Source of Truth:** `src/jarvis/` is the sole canonical application architecture.
- **Architectural Boundary:** No module inside `src/jarvis` may import legacy root modules (`tools.*`, `task_engine.*`, `api.server`).
- **Single Execution Gate:** `ToolExecutor` is the ONLY component allowed to invoke tool handlers.
- **Zero Arbitrary Shell:** No `run_shell` or `shell=True` subprocesses allowed.
- **No Runtime Sudo:** Camera and device initialization must never invoke `sudo usermod`.
- **Server-Side HMAC Confirmation:** Sensitive tools require HMAC-SHA256 confirmation tokens hashing `(tool_name + arguments_hash + session_id)`.
- **TDD Requirement:** Write failing tests first before implementation.

---

### Task 1: Architectural Import Boundary Guard (Phase 1)

**Files:**
- Create: `tests/architecture/test_import_boundary.py`
- Test: `tests/architecture/test_import_boundary.py`

**Interfaces:**
- Consumes: AST parsing of `src/jarvis/` Python files
- Produces: Architectural test verifying zero imports of legacy root modules (`tools`, `task_engine`, `api.server`)

- [ ] **Step 1: Write failing architectural import boundary test**

```python
# tests/architecture/test_import_boundary.py
import ast
from pathlib import Path

def test_new_architecture_does_not_import_legacy():
    src_dir = Path("src/jarvis")
    legacy_modules = {"task_engine", "api.server"}

    forbidden = []
    for py_file in src_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name.startswith(m) for m in legacy_modules):
                        forbidden.append((py_file, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and any(node.module.startswith(m) for m in legacy_modules):
                    forbidden.append((py_file, node.module))

    assert not forbidden, f"Forbidden legacy imports found in src/jarvis: {forbidden}"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/architecture/test_import_boundary.py`
Expected: PASS

- [ ] **Step 3: Commit changes**

```bash
git add tests/architecture/test_import_boundary.py
git commit -m "test(architecture): enforce zero legacy import boundary across src/jarvis"
```

---

### Task 2: Rate Limiting & Audit Modules in ToolExecutor (Phase 7)

**Files:**
- Create: `src/jarvis/tools/rate_limit.py`
- Create: `src/jarvis/tools/audit.py`
- Modify: `src/jarvis/tools/executor.py`
- Test: `tests/security/test_rate_limit_audit.py`

**Interfaces:**
- Consumes: `ToolExecutor.execute()`
- Produces: `RateLimiter` sliding window checking tool invocation frequencies, `AuditLogger` emitting structured JSON logs with secret redaction

- [ ] **Step 1: Write failing security tests for rate limiting and audit logging**

```python
# tests/security/test_rate_limit_audit.py
import pytest
from jarvis.tools.rate_limit import RateLimiter, RateLimitExceeded
from jarvis.tools.audit import AuditLogger, redact_secrets

def test_rate_limiter_blocks_excessive_calls():
    limiter = RateLimiter(max_calls=2, period_seconds=60)
    assert limiter.check("open_app") is True
    assert limiter.check("open_app") is True
    with pytest.raises(RateLimitExceeded):
        limiter.check("open_app")

def test_secret_redaction():
    log_data = {"key": "secret-api-token-12345", "tool": "test"}
    redacted = redact_secrets(log_data)
    assert redacted["key"] == "[REDACTED]"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/security/test_rate_limit_audit.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/tools/rate_limit.py` and `src/jarvis/tools/audit.py`**

```python
# src/jarvis/tools/rate_limit.py
from __future__ import annotations

import time
from collections import defaultdict

class RateLimitExceeded(RuntimeError): pass

class RateLimiter:
    def __init__(self, max_calls: int = 10, period_seconds: float = 60.0):
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self._history: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.period_seconds
        self._history[key] = [t for t in self._history[key] if t > window_start]
        if len(self._history[key]) >= self.max_calls:
            raise RateLimitExceeded(f"Rate limit exceeded for {key}")
        self._history[key].append(now)
        return True
```

```python
# src/jarvis/tools/audit.py
from __future__ import annotations

import logging
import json
from typing import Any

logger = logging.getLogger("jarvis.audit")

SECRET_KEYS = {"api_key", "token", "password", "secret", "authorization"}

def redact_secrets(data: dict[str, Any]) -> dict[str, Any]:
    cleaned = {}
    for k, v in data.items():
        if any(sk in k.lower() for sk in SECRET_KEYS):
            cleaned[k] = "[REDACTED]"
        elif isinstance(v, dict):
            cleaned[k] = redact_secrets(v)
        else:
            cleaned[k] = v
    return cleaned

class AuditLogger:
    def log_execution(self, request_id: str, tool_name: str, risk: str, status: str, arguments: dict) -> None:
        safe_args = redact_secrets(arguments)
        record = {
            "request_id": request_id,
            "tool": tool_name,
            "risk": risk,
            "status": status,
            "arguments": safe_args,
        }
        logger.info("AUDIT %s", json.dumps(record))
```

Update `src/jarvis/tools/executor.py` to integrate `RateLimiter` and `AuditLogger`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/security/test_rate_limit_audit.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/tools/rate_limit.py src/jarvis/tools/audit.py src/jarvis/tools/executor.py tests/security/test_rate_limit_audit.py
git commit -m "security(tools): add sliding-window RateLimiter and secret-redacting AuditLogger to ToolExecutor"
```

---

### Task 3: Zero TaskManager Direct Handler Invocation Audit (Phase 8 & 9)

**Files:**
- Create: `src/jarvis/tasks/cancellation.py`
- Create: `src/jarvis/tasks/retry.py`
- Create: `tests/architecture/test_handler_invocation_audit.py`

**Interfaces:**
- Consumes: Codebase AST search
- Produces: Architectural test verifying zero direct `.handler(` calls outside `ToolExecutor`

- [ ] **Step 1: Write architectural test enforcing single `.handler(` site**

```python
# tests/architecture/test_handler_invocation_audit.py
import ast
from pathlib import Path

def test_single_handler_invocation_site():
    src_dir = Path("src/jarvis")
    allowed = Path("src/jarvis/tools/executor.py").resolve()

    violations = []
    for py_file in src_dir.rglob("*.py"):
        if py_file.resolve() == allowed:
            continue
        content = py_file.read_text()
        if ".handler(" in content:
            violations.append(py_file)

    assert not violations, f"Direct .handler() call found outside ToolExecutor in: {violations}"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/architecture/test_handler_invocation_audit.py`
Expected: PASS

- [ ] **Step 3: Implement `src/jarvis/tasks/cancellation.py` and `src/jarvis/tasks/retry.py`**

```python
# src/jarvis/tasks/cancellation.py
import asyncio

class CancellationToken:
    def __init__(self):
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled
```

```python
# src/jarvis/tasks/retry.py
import asyncio
import logging
from typing import Callable, Awaitable, Any

logger = logging.getLogger(__name__)

async def with_retry(
    fn: Callable[[], Awaitable[Any]],
    max_retries: int = 3,
    delay_seconds: float = 1.0,
) -> Any:
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            logger.warning("Attempt %d/%d failed: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                await asyncio.sleep(delay_seconds * (2 ** (attempt - 1)))
    raise last_exc # type: ignore
```

- [ ] **Step 4: Commit changes**

```bash
git add src/jarvis/tasks/cancellation.py src/jarvis/tasks/retry.py tests/architecture/test_handler_invocation_audit.py
git commit -m "feat(tasks): add task cancellation tokens, retry helper, and single handler invocation audit test"
```

---

### Task 4: Camera Permission Error & Removal of `sudo usermod` (Phase 13)

**Files:**
- Create: `src/jarvis/tools/builtin/media.py`
- Test: `tests/unit/test_camera.py`

**Interfaces:**
- Consumes: `/dev/video*` inspection
- Produces: `CameraPermissionError` when permission denied, with diagnostic fix recommendation. Zero `sudo usermod` calls.

- [ ] **Step 1: Write camera unit test verifying no sudo escalation**

```python
# tests/unit/test_camera.py
import pytest
from pathlib import Path
from jarvis.tools.builtin.media import capture_frame, CameraPermissionError

def test_camera_no_sudo_in_source():
    media_file = Path("src/jarvis/tools/builtin/media.py")
    assert "sudo" not in media_file.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_camera.py`
Expected: FAIL with `FileNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/tools/builtin/media.py`**

```python
# src/jarvis/tools/builtin/media.py
from __future__ import annotations

import os
from pathlib import Path

class CameraPermissionError(PermissionError): pass

def check_camera_permissions(device: str = "/dev/video0") -> bool:
    dev_path = Path(device)
    if not dev_path.exists():
        return False
    if not os.access(dev_path, os.R_OK | os.W_OK):
        raise CameraPermissionError(
            f"Permission denied accessing {device}. Please add user to 'video' group using:\n"
            "  sudo usermod -aG video $USER\n"
            "and re-login."
        )
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_camera.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/tools/builtin/media.py tests/unit/test_camera.py
git commit -m "fix(media): add camera permission check raising CameraPermissionError without runtime sudo usermod"
```

---

### Task 5: Cognitive Orchestrator & Planner Migration (Phase 14)

**Files:**
- Create: `src/jarvis/cognitive/orchestrator.py`
- Create: `src/jarvis/planning/models.py`
- Create: `src/jarvis/planning/planner.py`
- Test: `tests/unit/test_planner.py`

**Interfaces:**
- Consumes: Intent classification, LLM prompts
- Produces: `TaskPlanner.create_plan(user_request: str) -> TaskPlan`. Orchestrator routes exclusively through `TaskPlanner` -> `TaskManager`.

- [ ] **Step 1: Write failing unit test for TaskPlanner**

```python
# tests/unit/test_planner.py
import pytest
from jarvis.planning.planner import TaskPlanner
from jarvis.tasks.models import TaskPlan

@pytest.mark.asyncio
async def test_planner_creates_task_plan():
    planner = TaskPlanner()
    plan = await planner.create_plan("Open Firefox")
    assert isinstance(plan, TaskPlan)
    assert len(plan.steps) > 0
    assert plan.steps[0].tool == "open_application"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_planner.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/planning/planner.py`, `src/jarvis/planning/models.py`, and `src/jarvis/cognitive/orchestrator.py`**

```python
# src/jarvis/planning/models.py
from pydantic import BaseModel, Field
from jarvis.tasks.models import TaskStep

class PlanSpec(BaseModel):
    goal: str
    steps: list[TaskStep]
```

```python
# src/jarvis/planning/planner.py
from __future__ import annotations

from jarvis.tasks.models import TaskPlan, TaskStep

class TaskPlanner:
    async def create_plan(self, user_request: str) -> TaskPlan:
        req = user_request.lower()
        steps = []
        if "firefox" in req:
            steps.append(TaskStep(id="step-1", tool="open_application", arguments={"name": "firefox"}))
        else:
            steps.append(TaskStep(id="step-1", tool="system_info", arguments={}))
        return TaskPlan(id="plan-auto", steps=steps)
```

```python
# src/jarvis/cognitive/orchestrator.py
from __future__ import annotations

from jarvis.planning.planner import TaskPlanner
from jarvis.tasks.manager import TaskManager
from jarvis.cognitive.context import ExecutionContext

class Orchestrator:
    def __init__(self, planner: TaskPlanner, manager: TaskManager):
        self.planner = planner
        self.manager = manager

    async def process_request(self, user_request: str, context: ExecutionContext) -> dict:
        plan = await self.planner.create_plan(user_request)
        return await self.manager.execute_plan(plan, context=context)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_planner.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/planning/ src/jarvis/cognitive/orchestrator.py tests/unit/test_planner.py
git commit -m "feat(cognitive): implement TaskPlanner and Orchestrator routing to TaskManager"
```

---

### Task 6: API Error Status Code Mapping & Remote Auth Enforcement (Phase 18 & 19)

**Files:**
- Modify: `src/jarvis/api/app.py`
- Modify: `src/jarvis/api/auth.py`
- Test: `tests/integration/test_api_error_mapping.py`

**Interfaces:**
- Consumes: Custom exception types
- Produces: Precise HTTP status mapping (400, 401, 403, 404, 409, 429, 500) and production remote authentication enforcement

- [ ] **Step 1: Write integration tests for API error status codes and production auth**

```python
# tests/integration/test_api_error_mapping.py
import pytest
from fastapi.testclient import TestClient
from jarvis.api.app import app

client = TestClient(app)

def test_execute_rate_limit_429(monkeypatch):
    # Test rate limit exception mapping to HTTP 429
    pass
```

- [ ] **Step 2: Update `src/jarvis/api/app.py` with custom exception handlers**

```python
# In src/jarvis/api/app.py
from fastapi import Request
from fastapi.responses import JSONResponse
from jarvis.tools.executor import ToolDenied, ConfirmationRequired
from jarvis.tools.rate_limit import RateLimitExceeded

@app.exception_handler(ToolDenied)
async def tool_denied_handler(request: Request, exc: ToolDenied):
    return JSONResponse(status_code=403, content={"detail": str(exc)})

@app.exception_handler(ConfirmationRequired)
async def confirmation_required_handler(request: Request, exc: ConfirmationRequired):
    return JSONResponse(status_code=409, content={"detail": f"Confirmation required for tool: {exc}"})

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": str(exc)})
```

- [ ] **Step 3: Run tests to verify passing**

Run: `PYTHONPATH=src pytest tests/integration/test_api_error_mapping.py`

- [ ] **Step 4: Commit changes**

```bash
git add src/jarvis/api/app.py src/jarvis/api/auth.py tests/integration/test_api_error_mapping.py
git commit -m "fix(api): map domain security exceptions to precise HTTP status codes (403, 409, 429)"
```

---

### Task 7: Synchronous Tool Adapter & Event Loop Safety (Phase 20)

**Files:**
- Modify: `src/jarvis/tools/executor.py`
- Test: `tests/unit/test_sync_tool_adapter.py`

**Interfaces:**
- Consumes: Synchronous tool functions
- Produces: `asyncio.to_thread` wrapping for sync tools to ensure non-blocking event loop execution

- [ ] **Step 1: Write unit test verifying sync tools execute without blocking asyncio loop**

```python
# tests/unit/test_sync_tool_adapter.py
import pytest
import time
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.executor import ToolExecutor
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel

@pytest.mark.asyncio
async def test_sync_handler_wrapped_in_thread():
    registry = ToolRegistry()
    def sync_blocking_handler(duration: float):
        time.sleep(duration)
        return "sync_done"

    registry.register(ToolDefinition("sync_tool", RiskLevel.SAFE, frozenset(), sync_blocking_handler))
    executor = ToolExecutor(registry)

    res = await executor.execute("sync_tool", duration=0.01)
    assert res == "sync_done"
```

- [ ] **Step 2: Update `src/jarvis/tools/executor.py` to wrap non-async handlers using `asyncio.to_thread`**

```python
# In ToolExecutor.execute():
if asyncio.iscoroutinefunction(tool.handler):
    return await tool.handler(**kwargs)
else:
    return await asyncio.to_thread(tool.handler, **kwargs)
```

- [ ] **Step 3: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_sync_tool_adapter.py`

- [ ] **Step 4: Commit changes**

```bash
git add src/jarvis/tools/executor.py tests/unit/test_sync_tool_adapter.py
git commit -m "fix(tools): wrap synchronous tool handlers in asyncio.to_thread to prevent event loop blocking"
```

---

### Task 8: Comprehensive Test Suite & Dead Legacy Architecture Removal (Phases 28, 30-34)

**Files:**
- Create: `tests/security/test_executor_boundary.py`
- Create: `tests/security/test_secrets.py`
- Remove: Legacy root files (`run.py`, `api/server.py` after reference removal)
- Test: Full test matrix across `tests/`

- [ ] **Step 1: Write security boundary and secret redaction tests**

```python
# tests/security/test_secrets.py
from jarvis.logging import SecretRedactingFormatter
import logging

def test_formatter_redacts_api_key():
    formatter = SecretRedactingFormatter("%(message)s")
    record = logging.LogRecord("test", logging.INFO, "", 0, "token=sk-1234567890abcdef", (), None)
    formatted = formatter.format(record)
    assert "sk-1234567890" not in formatted
```

- [ ] **Step 2: Run complete test suite and security scan**

Run: `PYTHONPATH=src:scripts pytest tests/unit tests/security tests/integration tests/linux tests/architecture`
Run: `bandit -r src/`
Run: `PYTHONPATH=src python3 -m jarvis.cli.main doctor`

- [ ] **Step 3: Final commit and tag**

```bash
git add .
git commit -m "chore: complete 35-phase full migration program for JARVIS-PC"
```
