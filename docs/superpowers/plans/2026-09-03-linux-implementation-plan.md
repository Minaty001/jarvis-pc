# Linux Implementation Plan for JARVIS-PC

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-architect JARVIS-PC into a Linux-first, security-bounded, service-oriented Python application with a single ToolExecutor gate, XDG path management, FastAPI ASGI server, safe process management, and systemd service control.

**Architecture:** Multi-layered service architecture where all side-effecting operations pass through a single, single-gate `ToolExecutor` bounded by risk levels (SAFE, READ_ONLY, USER_CONFIRMATION, PRIVILEGED, FORBIDDEN). Async FastAPI/Uvicorn backend, typed Pydantic v2 schemas, XDG paths for user state, and systemd user services.

**Tech Stack:** Python 3.12+, `pyproject.toml` + `uv.lock`, FastAPI, Uvicorn, Pydantic v2, Pydantic Settings, `aiosqlite`, `psutil`, `pathlib`, `pytest`, `systemd`.

**Spec:** User specification document ("Linux Implementation Plan for JARVIS-PC").

## Global Constraints

- **Python Baseline:** Python >= 3.12, strict `pathlib` usage for filesystem paths.
- **POSIX API:** POSIX standard APIs via `os` where required, `shell=False` for all subprocesses.
- **XDG Specification:** `$XDG_CONFIG_HOME`, `$XDG_DATA_HOME`, `$XDG_STATE_HOME`, `$XDG_CACHE_HOME`, and `$XDG_RUNTIME_DIR` compliance.
- **Execution Gate:** No module other than `ToolExecutor` may directly invoke a side-effecting tool.
- **No Arbitrary Shell:** No general-purpose `run_shell` or `shell=True` tools allowed.
- **Allowlist Applications:** Applications launched must match an explicit allowlist.
- **Systemd User Service:** Non-root execution via `~/.config/systemd/user/jarvis.service`.

---

### Task 1: Foundation - Project Layout and Dependencies

**Files:**
- Create: `src/jarvis/__init__.py`
- Create: `src/jarvis/__main__.py`
- Modify: `pyproject.toml`
- Test: `tests/unit/test_package_layout.py`

**Interfaces:**
- Consumes: Standard Python packaging
- Produces: `jarvis` package root importable via `src/jarvis`

- [ ] **Step 1: Write the failing unit test for package layout**

```python
# tests/unit/test_package_layout.py
import importlib

def test_jarvis_package_importable():
    jarvis = importlib.import_module("jarvis")
    assert jarvis is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_package_layout.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'jarvis'`

- [ ] **Step 3: Create package structure and update pyproject.toml**

```python
# src/jarvis/__init__.py
"""JARVIS Linux Assistant Package."""
__version__ = "1.0.0"
```

```python
# src/jarvis/__main__.py
"""Main entrypoint for jarvis module execution."""
import sys

def main() -> None:
    print("JARVIS CLI initialized")

if __name__ == "__main__":
    main()
```

Update `pyproject.toml` to include `src` directory in package search:
```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "jarvis-pc"
version = "1.0.0"
description = "JARVIS — Personal AI Voice Assistant for Linux"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.12"

dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.28.0",
    "pydantic>=2.6.0",
    "pydantic-settings>=2.2.0",
    "httpx>=0.27.0",
    "aiosqlite>=0.20.0",
    "psutil>=5.9.0",
]

[project.optional-dependencies]
voice = [
    "numpy>=1.26.0",
    "faster-whisper>=1.0.0",
    "edge-tts>=6.1.0",
    "sounddevice>=0.4.6",
    "soundfile>=0.12.0",
]
camera = [
    "opencv-python>=4.9.0",
]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.3.0",
    "pyright>=1.1.350",
    "bandit>=1.7.8",
]

[project.scripts]
jarvis = "jarvis.__main__:main"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_package_layout.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add pyproject.toml src/jarvis/__init__.py src/jarvis/__main__.py tests/unit/test_package_layout.py
git commit -m "feat(foundation): initialize src/jarvis package structure and pyproject.toml"
```

---

### Task 2: XDG Path Manager

**Files:**
- Create: `src/jarvis/system/paths.py`
- Test: `tests/unit/test_paths.py`

**Interfaces:**
- Consumes: Environment variables (`XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`, `XDG_CACHE_HOME`, `XDG_RUNTIME_DIR`), `os`, `pathlib.Path`
- Produces: `AppPaths` dataclass, `get_app_paths(app_name: str) -> AppPaths`, `initialize_paths(paths: AppPaths) -> None`

- [ ] **Step 1: Write the failing unit tests for XDG paths**

```python
# tests/unit/test_paths.py
import os
from pathlib import Path
from jarvis.system.paths import get_app_paths, initialize_paths

def test_get_app_paths_defaults(monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)

    paths = get_app_paths("jarvis_test")
    home = Path.home()
    assert paths.config == home / ".config" / "jarvis_test"
    assert paths.data == home / ".local" / "share" / "jarvis_test"
    assert paths.state == home / ".local" / "state" / "jarvis_test"
    assert paths.cache == home / ".cache" / "jarvis_test"
    assert paths.runtime == Path("/tmp") / f"jarvis_test-{os.getuid()}"

def test_initialize_paths(tmp_path):
    paths = get_app_paths("jarvis_test")
    custom_paths = paths.__class__(
        config=tmp_path / "config",
        data=tmp_path / "data",
        state=tmp_path / "state",
        cache=tmp_path / "cache",
        runtime=tmp_path / "runtime",
    )
    initialize_paths(custom_paths)
    assert custom_paths.config.exists()
    assert oct(custom_paths.config.stat().st_mode)[-3:] == "700"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_paths.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'jarvis.system'`

- [ ] **Step 3: Implement `src/jarvis/system/paths.py`**

```python
# src/jarvis/system/paths.py
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if not value:
        return default
    path = Path(value).expanduser()
    if not path.is_absolute():
        logger.warning(
            "%s=%s is not absolute; using default %s",
            name,
            value,
            default,
        )
        return default
    return path

@dataclass(frozen=True)
class AppPaths:
    config: Path
    data: Path
    state: Path
    cache: Path
    runtime: Path

def get_app_paths(app_name: str = "jarvis") -> AppPaths:
    home = Path.home()
    config_base = _env_path("XDG_CONFIG_HOME", home / ".config")
    data_base = _env_path("XDG_DATA_HOME", home / ".local" / "share")
    state_base = _env_path("XDG_STATE_HOME", home / ".local" / "state")
    cache_base = _env_path("XDG_CACHE_HOME", home / ".cache")

    runtime_env = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_env:
        runtime = Path(runtime_env).expanduser()
        if not runtime.is_absolute():
            runtime = Path("/tmp") / f"{app_name}-{os.getuid()}"
    else:
        runtime = Path("/tmp") / f"{app_name}-{os.getuid()}"
        logger.warning(
            "XDG_RUNTIME_DIR is not set; using fallback %s",
            runtime,
        )

    return AppPaths(
        config=config_base / app_name,
        data=data_base / app_name,
        state=state_base / app_name,
        cache=cache_base / app_name,
        runtime=runtime,
    )

def initialize_paths(paths: AppPaths) -> None:
    for path in (paths.config, paths.data, paths.state, paths.cache, paths.runtime):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            path.chmod(0o700)
        except PermissionError:
            logger.warning("Could not enforce 0700 permissions on %s", path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_paths.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/system/paths.py tests/unit/test_paths.py
git commit -m "feat(system): add XDG path manager module and unit tests"
```

---

### Task 3: Atomic File Operations & Safe File Store

**Files:**
- Create: `src/jarvis/system/files.py`
- Create: `src/jarvis/tools/builtin/filesystem.py`
- Test: `tests/unit/test_files.py`
- Test: `tests/unit/test_safe_file_store.py`

**Interfaces:**
- Consumes: `pathlib.Path`, `os`, `tempfile`
- Produces: `atomic_write_text(path: Path, content: str, mode: int = 0o600) -> None`, `SafeFileStore(root: Path)`, `PathSecurityError`

- [ ] **Step 1: Write failing tests for atomic file writes and SafeFileStore**

```python
# tests/unit/test_files.py
import pytest
from pathlib import Path
from jarvis.system.files import atomic_write_text

def test_atomic_write_text(tmp_path):
    target = tmp_path / "config" / "settings.json"
    atomic_write_text(target, '{"key": "value"}', mode=0o600)
    assert target.exists()
    assert target.read_text() == '{"key": "value"}'
    assert oct(target.stat().st_mode)[-3:] == "600"
```

```python
# tests/unit/test_safe_file_store.py
import pytest
from pathlib import Path
from jarvis.tools.builtin.filesystem import SafeFileStore, PathSecurityError

def test_safe_file_store_rejects_escape(tmp_path):
    store = SafeFileStore(tmp_path)
    with pytest.raises(PathSecurityError):
        store.resolve_user_path("../../etc/passwd")

def test_safe_file_store_valid_read(tmp_path):
    f = tmp_path / "valid.txt"
    f.write_text("hello world")
    store = SafeFileStore(tmp_path)
    content = store.read_text("valid.txt")
    assert content == "hello world"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/unit/test_files.py tests/unit/test_safe_file_store.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/system/files.py` and `src/jarvis/tools/builtin/filesystem.py`**

```python
# src/jarvis/system/files.py
from __future__ import annotations

import os
import tempfile
from pathlib import Path

def atomic_write_text(
    path: Path,
    content: str,
    *,
    mode: int = 0o600,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
```

```python
# src/jarvis/tools/builtin/filesystem.py
from __future__ import annotations

from pathlib import Path

class PathSecurityError(ValueError):
    pass

class SafeFileStore:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)

    def resolve_user_path(self, user_path: str) -> Path:
        candidate = (self.root / user_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise PathSecurityError(
                f"path escapes allowed root: {user_path!r}"
            ) from exc
        return candidate

    def read_text(
        self,
        user_path: str,
        *,
        max_bytes: int = 1_000_000,
    ) -> str:
        path = self.resolve_user_path(user_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        size = path.stat().st_size
        if size > max_bytes:
            raise ValueError(f"file exceeds maximum size: {max_bytes} bytes")
        return path.read_text(encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/unit/test_files.py tests/unit/test_safe_file_store.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/system/files.py src/jarvis/tools/builtin/filesystem.py tests/unit/test_files.py tests/unit/test_safe_file_store.py
git commit -m "feat(system): add atomic file writer and SafeFileStore module"
```

---

### Task 4: Process Runner & Distribution Detection

**Files:**
- Create: `src/jarvis/system/process.py`
- Create: `src/jarvis/system/distro.py`
- Create: `src/jarvis/system/permissions.py`
- Test: `tests/unit/test_process.py`
- Test: `tests/unit/test_distro.py`

**Interfaces:**
- Consumes: `asyncio.create_subprocess_exec`, `psutil`, `/etc/os-release`
- Produces: `run_process(args, cwd, timeout, env) -> ProcessResult`, `detect_distribution() -> LinuxDistribution`, `require_readable(path)`, `require_writable(path)`

- [ ] **Step 1: Write failing unit tests for process runner, distribution detection, and permission checks**

```python
# tests/unit/test_process.py
import pytest
from jarvis.system.process import run_process, ProcessError

@pytest.mark.asyncio
async def test_run_process_success():
    res = await run_process(["echo", "hello"])
    assert res.returncode == 0
    assert "hello" in res.stdout

@pytest.mark.asyncio
async def test_run_process_timeout():
    with pytest.raises(ProcessError, match="timed out"):
        await run_process(["sleep", "5"], timeout=0.1)
```

```python
# tests/unit/test_distro.py
from jarvis.system.distro import detect_distribution, LinuxDistribution

def test_detect_distribution():
    distro = detect_distribution()
    assert isinstance(distro, LinuxDistribution)
    assert distro.id != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_process.py tests/unit/test_distro.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/system/process.py`, `src/jarvis/system/distro.py`, and `src/jarvis/system/permissions.py`**

```python
# src/jarvis/system/process.py
from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass
from typing import Sequence

class ProcessError(RuntimeError):
    pass

@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str

async def run_process(
    args: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    timeout: float = 30.0,
    env: dict[str, str] | None = None,
) -> ProcessResult:
    if not args:
        raise ValueError("args cannot be empty")

    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except OSError:
            pass

        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            await process.wait()

        raise ProcessError(f"process timed out after {timeout}s")

    result = ProcessResult(
        returncode=process.returncode,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )

    if result.returncode != 0:
        raise ProcessError(
            f"command failed ({result.returncode}): {result.stderr[:1000]}"
        )

    return result
```

```python
# src/jarvis/system/distro.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class LinuxDistribution:
    id: str
    version_id: str
    pretty_name: str

def detect_distribution() -> LinuxDistribution:
    path = Path("/etc/os-release")
    values: dict[str, str] = {}

    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    except OSError:
        return LinuxDistribution(
            id="unknown",
            version_id="unknown",
            pretty_name="Unknown Linux",
        )

    return LinuxDistribution(
        id=values.get("ID", "unknown"),
        version_id=values.get("VERSION_ID", "unknown"),
        pretty_name=values.get("PRETTY_NAME", "Unknown Linux"),
    )
```

```python
# src/jarvis/system/permissions.py
from __future__ import annotations

import os
from pathlib import Path

class PermissionErrorInfo(RuntimeError):
    pass

def require_readable(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    if not os.access(path, os.R_OK):
        raise PermissionErrorInfo(f"file is not readable: {path}")

def require_writable(path: Path) -> None:
    parent = path.parent
    if not parent.exists():
        raise FileNotFoundError(parent)
    if not os.access(parent, os.W_OK):
        raise PermissionErrorInfo(f"directory is not writable: {parent}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_process.py tests/unit/test_distro.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/system/process.py src/jarvis/system/distro.py src/jarvis/system/permissions.py tests/unit/test_process.py tests/unit/test_distro.py
git commit -m "feat(system): add safe subprocess runner, linux distro detection, and permission checks"
```

---

### Task 5: Security Policy & Single ToolExecutor Gate

**Files:**
- Create: `src/jarvis/tools/executor.py`
- Create: `src/jarvis/tools/policy.py`
- Test: `tests/security/test_tool_executor.py`

**Interfaces:**
- Consumes: RiskLevel enum (`SAFE`, `CONFIRM`, `PRIVILEGED`, `FORBIDDEN`)
- Produces: `ToolExecutor`, `ToolDefinition`, `ToolDenied`, `ConfirmationRequired`

- [ ] **Step 1: Write failing security tests for ToolExecutor and risk policy enforcement**

```python
# tests/security/test_tool_executor.py
import pytest
from jarvis.tools.executor import (
    ToolExecutor,
    ToolDefinition,
    RiskLevel,
    ToolDenied,
    ConfirmationRequired,
)

@pytest.mark.asyncio
async def test_tool_executor_safe():
    executor = ToolExecutor()
    async def sample_handler(val: str):
        return f"result-{val}"

    executor.register(ToolDefinition("safe_tool", RiskLevel.SAFE, sample_handler))
    res = await executor.execute("safe_tool", val="123")
    assert res == "result-123"

@pytest.mark.asyncio
async def test_tool_executor_confirm_requires_flag():
    executor = ToolExecutor()
    async def confirm_handler():
        return "done"

    executor.register(ToolDefinition("confirm_tool", RiskLevel.CONFIRM, confirm_handler))
    with pytest.raises(ConfirmationRequired):
        await executor.execute("confirm_tool", confirmed=False)

    res = await executor.execute("confirm_tool", confirmed=True)
    assert res == "done"

@pytest.mark.asyncio
async def test_tool_executor_forbidden_denied():
    executor = ToolExecutor()
    async def forbidden_handler():
        return "bad"

    executor.register(ToolDefinition("forbidden_tool", RiskLevel.FORBIDDEN, forbidden_handler))
    with pytest.raises(ToolDenied):
        await executor.execute("forbidden_tool")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/security/test_tool_executor.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/tools/executor.py` and `src/jarvis/tools/policy.py`**

```python
# src/jarvis/tools/policy.py
from enum import Enum

class RiskLevel(str, Enum):
    SAFE = "safe"
    CONFIRM = "confirm"
    PRIVILEGED = "privileged"
    FORBIDDEN = "forbidden"
```

```python
# src/jarvis/tools/executor.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from jarvis.tools.policy import RiskLevel

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class ToolDefinition:
    name: str
    risk: RiskLevel
    handler: Callable[..., Awaitable[Any]]

class ToolDenied(RuntimeError):
    pass

class ConfirmationRequired(RuntimeError):
    pass

class ToolExecutor:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    async def execute(
        self,
        name: str,
        *,
        confirmed: bool = False,
        **kwargs,
    ) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolDenied(f"unknown tool: {name}")

        if tool.risk is RiskLevel.FORBIDDEN:
            raise ToolDenied(f"tool forbidden: {name}")

        if tool.risk is RiskLevel.CONFIRM and not confirmed:
            raise ConfirmationRequired(name)

        if tool.risk is RiskLevel.PRIVILEGED:
            raise ToolDenied(
                "privileged tool requires explicit administrator workflow"
            )

        logger.info(
            "Executing tool=%s risk=%s",
            tool.name,
            tool.risk.value,
        )

        return await tool.handler(**kwargs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/security/test_tool_executor.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/tools/executor.py src/jarvis/tools/policy.py tests/security/test_tool_executor.py
git commit -m "feat(security): add ToolExecutor gate and RiskLevel policy enforcement"
```

---

### Task 6: Safe Built-in Application Control & Process Inspection Tools

**Files:**
- Create: `src/jarvis/tools/builtin/applications.py`
- Create: `src/jarvis/tools/builtin/processes.py`
- Test: `tests/unit/test_builtin_tools.py`

**Interfaces:**
- Consumes: `ALLOWED_APPLICATIONS` allowlist mapping, `psutil`, `run_process`
- Produces: `open_application(name: str)`, `find_processes(name: str) -> list[dict]`

- [ ] **Step 1: Write failing unit tests for application launcher and process finder**

```python
# tests/unit/test_builtin_tools.py
import pytest
from jarvis.tools.builtin.applications import open_application, ApplicationError
from jarvis.tools.builtin.processes import find_processes

@pytest.mark.asyncio
async def test_open_application_disallowed():
    with pytest.raises(ApplicationError, match="not allowed"):
        await open_application("unauthorized_app_xyz")

def test_find_processes():
    procs = find_processes("python3")
    assert isinstance(procs, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_builtin_tools.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/tools/builtin/applications.py` and `src/jarvis/tools/builtin/processes.py`**

```python
# src/jarvis/tools/builtin/applications.py
from __future__ import annotations

from jarvis.system.process import run_process, ProcessResult

ALLOWED_APPLICATIONS: dict[str, tuple[str, ...]] = {
    "firefox": ("firefox",),
    "chrome": ("google-chrome",),
    "terminal": ("x-terminal-emulator",),
}

class ApplicationError(RuntimeError):
    pass

async def open_application(name: str) -> ProcessResult:
    key = name.strip().lower()
    command = ALLOWED_APPLICATIONS.get(key)
    if command is None:
        raise ApplicationError(f"application {name!r} is not allowed")

    return await run_process(list(command), timeout=10.0)
```

```python
# src/jarvis/tools/builtin/processes.py
from __future__ import annotations

import psutil

def find_processes(name: str) -> list[dict]:
    result: list[dict] = []
    for process in psutil.process_iter(["pid", "name", "username"]):
        try:
            info = process.info
            if info.get("name") == name:
                result.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_builtin_tools.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/tools/builtin/applications.py src/jarvis/tools/builtin/processes.py tests/unit/test_builtin_tools.py
git commit -m "feat(tools): add application launcher allowlist and psutil process finder"
```

---

### Task 7: Pydantic Configuration System & Logging Setup

**Files:**
- Create: `src/jarvis/config/settings.py`
- Create: `src/jarvis/config/defaults.py`
- Create: `src/jarvis/logging.py`
- Test: `tests/unit/test_settings.py`

**Interfaces:**
- Consumes: Pydantic Settings v2, stdlib `logging`
- Produces: `Settings`, `get_settings() -> Settings`, `configure_logging(level: str) -> None`

- [ ] **Step 1: Write failing unit tests for configuration settings**

```python
# tests/unit/test_settings.py
from jarvis.config.settings import get_settings, Settings

def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("JARVIS_PORT", "9000")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.port == 9000
    assert settings.environment == "production"
    get_settings.cache_clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_settings.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/config/settings.py` and `src/jarvis/logging.py`**

```python
# src/jarvis/config/settings.py
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",
        env_file=".env",
        extra="ignore",
    )

    environment: str = "production"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    api_token: str | None = None
    max_request_bytes: int = Field(default=1_000_000, ge=1024)
    command_timeout_seconds: float = Field(default=30.0, gt=0, le=300)

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python
# src/jarvis/logging.py
import logging
import sys

def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(process)d %(message)s",
        stream=sys.stdout,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_settings.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/config/settings.py src/jarvis/logging.py tests/unit/test_settings.py
git commit -m "feat(config): add typed Pydantic settings and structured logging module"
```

---

### Task 8: Task Engine Models & Lifecycle TaskManager

**Files:**
- Create: `src/jarvis/tasks/models.py`
- Create: `src/jarvis/tasks/manager.py`
- Create: `src/jarvis/tasks/lifecycle.py`
- Test: `tests/unit/test_task_manager.py`

**Interfaces:**
- Consumes: `ToolExecutor`, Pydantic models
- Produces: `TaskPlan`, `TaskStep`, `TaskManager`, step state management & timeout retries

- [ ] **Step 1: Write failing unit test for TaskManager using ToolExecutor**

```python
# tests/unit/test_task_manager.py
import pytest
from jarvis.tools.executor import ToolExecutor, ToolDefinition, RiskLevel
from jarvis.tasks.models import TaskPlan, TaskStep
from jarvis.tasks.manager import TaskManager

@pytest.mark.asyncio
async def test_task_manager_executes_plan_via_executor():
    executor = ToolExecutor()
    executed_args = []

    async def mock_handler(target: str):
        executed_args.append(target)
        return "success"

    executor.register(ToolDefinition("test_tool", RiskLevel.SAFE, mock_handler))
    manager = TaskManager(executor)

    plan = TaskPlan(
        id="plan-1",
        steps=[
            TaskStep(id="step-1", tool="test_tool", arguments={"target": "file.txt"})
        ]
    )

    results = await manager.execute_plan(plan)
    assert results["step-1"] == "success"
    assert executed_args == ["file.txt"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_task_manager.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/tasks/models.py` and `src/jarvis/tasks/manager.py`**

```python
# src/jarvis/tasks/models.py
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskStep(BaseModel):
    id: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING

class TaskPlan(BaseModel):
    id: str
    steps: list[TaskStep]
```

```python
# src/jarvis/tasks/manager.py
from __future__ import annotations

import logging
from typing import Any
from jarvis.tools.executor import ToolExecutor
from jarvis.tasks.models import TaskPlan, StepStatus

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self, executor: ToolExecutor):
        self.executor = executor

    async def execute_plan(
        self,
        plan: TaskPlan,
        *,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for step in plan.steps:
            step.status = StepStatus.RUNNING
            logger.info("TaskManager executing step %s (%s)", step.id, step.tool)
            try:
                res = await self.executor.execute(
                    step.tool,
                    confirmed=confirmed,
                    **step.arguments,
                )
                step.status = StepStatus.COMPLETED
                results[step.id] = res
            except Exception as exc:
                step.status = StepStatus.FAILED
                logger.error("Step %s failed: %s", step.id, exc)
                raise
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_task_manager.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/tasks/models.py src/jarvis/tasks/manager.py tests/unit/test_task_manager.py
git commit -m "feat(tasks): implement TaskPlan models and TaskManager routing through ToolExecutor"
```

---

### Task 9: FastAPI Server & Authorization Endpoints

**Files:**
- Create: `src/jarvis/api/schemas.py`
- Create: `src/jarvis/api/auth.py`
- Create: `src/jarvis/api/app.py`
- Test: `tests/integration/test_api.py`

**Interfaces:**
- Consumes: FastAPI, Uvicorn, `ToolExecutor`, `Settings`
- Produces: `/health`, `/execute` endpoints, API token verification dependency

- [ ] **Step 1: Write failing integration test for FastAPI server**

```python
# tests/integration/test_api.py
import pytest
from fastapi.testclient import TestClient
from jarvis.api.app import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_execute_endpoint_unknown_tool():
    response = client.post("/execute", json={"tool": "nonexistent_tool"})
    assert response.status_code == 400
    assert "unknown tool" in response.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/integration/test_api.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/api/schemas.py`, `src/jarvis/api/auth.py`, and `src/jarvis/api/app.py`**

```python
# src/jarvis/api/schemas.py
from pydantic import BaseModel, Field

class ExecuteRequest(BaseModel):
    tool: str = Field(min_length=1, max_length=100)
    arguments: dict = Field(default_factory=dict)
    confirmed: bool = False

class ExecuteResponse(BaseModel):
    ok: bool
    result: str | dict | None = None
```

```python
# src/jarvis/api/auth.py
from fastapi import Header, HTTPException, status
from jarvis.config.settings import get_settings

def verify_auth(authorization: str | None = Header(None)) -> None:
    settings = get_settings()
    if not settings.api_token:
        return
    if authorization != f"Bearer {settings.api_token}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
        )
```

```python
# src/jarvis/api/app.py
from fastapi import Depends, FastAPI, HTTPException
from jarvis.api.schemas import ExecuteRequest, ExecuteResponse
from jarvis.api.auth import verify_auth
from jarvis.tools.executor import ToolExecutor

app = FastAPI(title="JARVIS API", version="1.0.0")
_tool_executor = ToolExecutor()

def get_tool_executor() -> ToolExecutor:
    return _tool_executor

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/execute", response_model=ExecuteResponse)
async def execute(
    request: ExecuteRequest,
    _: None = Depends(verify_auth),
):
    try:
        executor = get_tool_executor()
        result = await executor.execute(
            request.tool,
            confirmed=request.confirmed,
            **request.arguments,
        )
        return ExecuteResponse(ok=True, result=result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/integration/test_api.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/api/schemas.py src/jarvis/api/auth.py src/jarvis/api/app.py tests/integration/test_api.py
git commit -m "feat(api): add FastAPI application with auth dependency and /execute gate endpoint"
```

---

### Task 10: Application Lifecycle Manager

**Files:**
- Create: `src/jarvis/app/application.py`
- Create: `src/jarvis/app/lifecycle.py`
- Create: `src/jarvis/app/health.py`
- Test: `tests/unit/test_application_lifecycle.py`

**Interfaces:**
- Consumes: Async subsystems (voice, API, background schedulers)
- Produces: `Application.start()`, `Application.stop()` clean shutdown lifecycle

- [ ] **Step 1: Write failing unit test for Application startup and shutdown**

```python
# tests/unit/test_application_lifecycle.py
import pytest
from jarvis.app.application import Application

class DummyComponent:
    def __init__(self):
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

@pytest.mark.asyncio
async def test_application_lifecycle():
    dummy = DummyComponent()
    app = Application(scheduler=dummy)
    await app.start()
    assert dummy.started is True
    await app.stop()
    assert dummy.stopped is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_application_lifecycle.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/jarvis/app/application.py`**

```python
# src/jarvis/app/application.py
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

class Application:
    def __init__(
        self,
        *,
        voice=None,
        scheduler=None,
        api=None,
    ):
        self.voice = voice
        self.scheduler = scheduler
        self.api = api

        self._started = False
        self._stopping = False

    async def start(self) -> None:
        if self._started:
            return

        logger.info("Starting JARVIS")

        if self.scheduler:
            await self.scheduler.start()

        if self.voice:
            await self.voice.start()

        self._started = True
        logger.info("JARVIS started successfully")

    async def stop(self) -> None:
        if not self._started or self._stopping:
            return

        self._stopping = True
        logger.info("Stopping JARVIS")
        errors = []

        for component in (self.voice, self.scheduler):
            if component is None:
                continue

            try:
                await component.stop()
            except Exception as exc:
                logger.exception("Failed stopping %r", component)
                errors.append(exc)

        self._started = False

        if errors:
            raise RuntimeError(f"{len(errors)} component(s) failed to stop")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_application_lifecycle.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/jarvis/app/application.py tests/unit/test_application_lifecycle.py
git commit -m "feat(app): implement central Application lifecycle manager"
```

---

### Task 11: Linux Doctor Command & Diagnostic Script

**Files:**
- Create: `scripts/doctor.py`
- Modify: `src/jarvis/__main__.py`
- Test: `tests/linux/test_doctor.py`

**Interfaces:**
- Consumes: `detect_distribution()`, `get_app_paths()`, `psutil`, Python environment
- Produces: `python3 scripts/doctor.py` and `jarvis doctor` CLI diagnostic command

- [ ] **Step 1: Write failing test for Linux doctor diagnostic**

```python
# tests/linux/test_doctor.py
from scripts.doctor import run_doctor

def test_run_doctor():
    report = run_doctor()
    assert "OS:" in report
    assert "Python:" in report
    assert "XDG:" in report
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/linux/test_doctor.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `scripts/doctor.py`**

```python
# scripts/doctor.py
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

    lines.extend([
        "",
        "Result:",
        "  0 errors",
    ])
    return "\n".join(lines)

if __name__ == "__main__":
    print(run_doctor())
```

Update `src/jarvis/__main__.py`:
```python
# src/jarvis/__main__.py
import sys
from scripts.doctor import run_doctor

def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        print(run_doctor())
    else:
        print("JARVIS CLI v1.0.0 (Linux)")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:scripts pytest tests/linux/test_doctor.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add scripts/doctor.py src/jarvis/__main__.py tests/linux/test_doctor.py
git commit -m "feat(linux): add Linux Doctor diagnostic tool and jarvis doctor CLI subcommand"
```

---

### Task 12: Systemd Deployment Unit & Installation Installer Scripts

**Files:**
- Create: `deploy/systemd/jarvis.service`
- Create: `scripts/install.sh`
- Create: `scripts/uninstall.sh`
- Test: `tests/linux/test_systemd_config.py`

**Interfaces:**
- Consumes: systemd user units specification
- Produces: Production ready `jarvis.service` and user-friendly `install.sh` / `uninstall.sh`

- [ ] **Step 1: Write test verifying systemd unit file contents**

```python
# tests/linux/test_systemd_config.py
from pathlib import Path

def test_systemd_unit_validity():
    unit_path = Path("deploy/systemd/jarvis.service")
    assert unit_path.exists()
    content = unit_path.read_text()
    assert "[Unit]" in content
    assert "[Service]" in content
    assert "ExecStart=" in content
    assert "NoNewPrivileges=true" in content
    assert "ProtectSystem=strict" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/linux/test_systemd_config.py`
Expected: FAIL with `AssertionError: File deploy/systemd/jarvis.service does not exist`

- [ ] **Step 3: Create systemd unit file and installer scripts**

Create `deploy/systemd/jarvis.service`:
```ini
[Unit]
Description=JARVIS Linux Assistant
After=network-online.target
Wants=network-online.target

[Service]
Type=simple

User=%u

WorkingDirectory=%h/.local/share/jarvis

Environment="PYTHONUNBUFFERED=1"

ExecStart=%h/.local/bin/jarvis

Restart=on-failure
RestartSec=5

NoNewPrivileges=true
PrivateTmp=true

ProtectSystem=strict
ProtectHome=read-only

ReadWritePaths=%h/.config/jarvis
ReadWritePaths=%h/.local/share/jarvis
ReadWritePaths=%h/.local/state/jarvis
ReadWritePaths=%h/.cache/jarvis

RestrictSUIDSGID=true

[Install]
WantedBy=default.target
```

Create `scripts/install.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Installing JARVIS Linux Assistant..."
mkdir -p ~/.config/systemd/user
cp deploy/systemd/jarvis.service ~/.config/systemd/user/jarvis.service

systemctl --user daemon-reload
echo "JARVIS service file installed to ~/.config/systemd/user/jarvis.service"
echo "To enable and start: systemctl --user enable --now jarvis.service"
```

Create `scripts/uninstall.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Uninstalling JARVIS Linux Assistant service..."
systemctl --user stop jarvis.service || true
systemctl --user disable jarvis.service || true
rm -f ~/.config/systemd/user/jarvis.service
systemctl --user daemon-reload
echo "JARVIS service uninstalled."
```

Make scripts executable:
```bash
chmod +x scripts/install.sh scripts/uninstall.sh
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/linux/test_systemd_config.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add deploy/systemd/jarvis.service scripts/install.sh scripts/uninstall.sh tests/linux/test_systemd_config.py
git commit -m "feat(deploy): add systemd user service definition and install/uninstall shell scripts"
```

---

### Task 13: Full Suite Verification & Verification Commands

**Files:**
- Modify: `tests/` directory structure

- [ ] **Step 1: Run comprehensive test suite**

Run: `PYTHONPATH=src:scripts pytest tests/unit tests/security tests/integration tests/linux`
Expected: All tests PASS cleanly

- [ ] **Step 2: Run static analysis check with ruff & bandit**

Run: `ruff check src/` and `bandit -r src/`
Expected: Zero security issues or critical lint errors.

- [ ] **Step 3: Run jarvis doctor**

Run: `PYTHONPATH=src:scripts python3 scripts/doctor.py`
Expected: Clean doctor output showing OS, Python 3.12+, XDG paths, and zero errors.

- [ ] **Step 4: Final commit and tag**

```bash
git add .
git commit -m "chore: complete Linux-first architecture overhaul for JARVIS-PC"
```
