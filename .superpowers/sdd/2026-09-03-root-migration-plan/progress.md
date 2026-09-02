# SDD ledger — plan: docs/superpowers/plans/2026-09-03-root-migration-plan.md

## Pre-flight Conflict Scan
| Task A | Task B | Shared Interface / File | Agrees? | Ruling / Notes |
|--------|--------|-------------------------|---------|----------------|
| Task 1 | Task 4 | `task_engine/manager.py` | Yes | Eliminates direct `.handler()` calls |
| Task 2 | Task 3 | `tools/builtin/shell_exec.py`, `camera.py` | Yes | Removes `shell=True` and `sudo usermod` |
| Task 3 | Task 6 | `ToolExecutor` + HMAC confirmation | Yes | Requires valid signed confirmation token |
| Task 4 | Task 6 | `run.py` & `src/jarvis/app/application.py` | Yes | Makes Application authoritative |
| Task 5 | Task 7 | `AuditLogger` + `RateLimiter` | Yes | Adds regex secret redaction & `asyncio.Lock()` |

Pre-flight scan complete: 0 conflicts found.
