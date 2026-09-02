# Task 2 Brief: CLI `run` persistent lifecycle with signal handling

**Fixes issue:** #20 (CLI run exits immediately)

**Depends on:** Task 1 (Application now has `run_until_stopped()` and `request_stop()`)

## Problem

`run_cli()` calls `asyncio.run(application.start())` which initializes components and returns immediately. The process exits.

## Target

`jarvis run` must:
1. Start Application
2. Block on `asyncio.Event` until SIGTERM/SIGINT
3. Gracefully stop Application
4. Exit

## Files to modify

### 1. MODIFY `src/jarvis/cli/main.py`

Update the `run` subcommand handler:

```python
elif parsed_args.subcommand == "run":
    print("Starting JARVIS v1.0.0...")
    application = app if app is not None else Application()
    asyncio.run(application.run_until_stopped())
```

Remove the `try/except RuntimeError` loop-detection code — `asyncio.run()` is always the entry.

### 2. WRITE TEST `tests/unit/test_cli_lifecycle.py`

```python
import asyncio
import pytest
from jarvis.app.application import Application


@pytest.mark.asyncio
async def test_application_run_until_stopped():
    """Application.run_until_stopped blocks until request_stop is called."""
    app = Application()
    task = asyncio.create_task(app.run_until_stopped())
    await asyncio.sleep(0.1)
    assert app.is_started
    app.request_stop()
    await task
    assert not app.is_started


@pytest.mark.asyncio
async def test_application_request_stop_before_start():
    """request_stop is safe to call before run_until_stopped."""
    app = Application()
    app.request_stop()  # Should not raise
```

## Execution steps

1. Write test `tests/unit/test_cli_lifecycle.py`
2. Run: `PYTHONPATH=src pytest tests/unit/test_cli_lifecycle.py`
3. Modify `src/jarvis/cli/main.py`
4. Run test again
5. Commit: `git add src/jarvis/cli/main.py tests/unit/test_cli_lifecycle.py && git commit -m "fix(cli): keep jarvis run alive with signal-based graceful shutdown"`
6. Write report to `/home/shanu/Desktop/jarvis-pc/.superpowers/sdd/2026-09-03-composition-root-plan/task-2-report.md`
