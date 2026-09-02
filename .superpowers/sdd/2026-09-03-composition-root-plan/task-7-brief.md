# Task 7 Brief: Fix `jarvis status` to check real service state

**Fixes issue:** #21 (fake status printing "operational" always)

## Problem

`jarvis status` hardcodes `print("JARVIS Status: operational")` without checking anything.

## Target

Check real service state:
1. `systemctl --user is-active jarvis.service`
2. HTTP health check `GET http://127.0.0.1:8000/health`
3. Report actual state with correct exit code

## Files to modify

### 1. MODIFY `src/jarvis/cli/main.py`

Add `check_status()` function:
```python
import subprocess
import urllib.request


def check_status() -> str:
    """Check real JARVIS service status."""
    # 1. Check systemd user service
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "jarvis.service"],
            capture_output=True, text=True, timeout=5
        )
        systemd_state = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        systemd_state = "unknown"

    # 2. Check health endpoint
    health_ok = False
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as resp:
            if resp.status == 200:
                health_ok = True
    except Exception:
        pass

    if systemd_state == "active" and health_ok:
        return "running"
    elif systemd_state == "active":
        return "starting"
    elif health_ok:
        return "running (not managed by systemd)"
    else:
        return "stopped"
```

Update the status subcommand:
```python
elif parsed_args.subcommand == "status":
    state = check_status()
    print(f"JARVIS Status: {state}")
    return 0 if "running" in state else 1
```

### 2. WRITE TEST `tests/unit/test_cli_status.py`

```python
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from jarvis.cli.main import check_status


def test_status_reports_stopped_when_nothing_running(monkeypatch):
    """When systemctl and health both fail, status should be 'stopped'."""
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **kw: MagicMock(stdout="inactive\n", returncode=3)
    )
    result = check_status()
    assert result == "stopped"


def test_status_does_not_hardcode_operational():
    """jarvis status must never hardcode 'operational'."""
    from pathlib import Path
    content = Path("src/jarvis/cli/main.py").read_text()
    assert "operational" not in content
```

## Execution steps

1. Write test `tests/unit/test_cli_status.py`
2. Run: `PYTHONPATH=src pytest tests/unit/test_cli_status.py`
3. Modify `src/jarvis/cli/main.py`
4. Run test again
5. Commit: `git add src/jarvis/cli/main.py tests/unit/test_cli_status.py && git commit -m "fix(cli): replace fake jarvis status with real systemd/health/PID checks"`
6. Write report to `/home/shanu/Desktop/jarvis-pc/.superpowers/sdd/2026-09-03-composition-root-plan/task-7-report.md`
