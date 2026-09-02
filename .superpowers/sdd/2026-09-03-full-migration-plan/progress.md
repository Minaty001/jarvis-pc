# SDD ledger — plan: docs/superpowers/plans/2026-09-03-full-migration-plan.md

## Pre-flight Conflict Scan
| Task A | Task B | Shared Interface / File | Agrees? | Ruling / Notes |
|--------|--------|-------------------------|---------|----------------|
| Task 1 | Task 2-8 | AST import scan | Yes | AST test verifies zero legacy imports inside src/jarvis |
| Task 2 | Task 6,7 | `RateLimiter` & `AuditLogger` | Yes | Integrated directly into `ToolExecutor.execute()` |
| Task 3 | Task 5,7 | AST handler invocation scan | Yes | AST test enforces single `.handler()` call site |
| Task 4 | Task 7 | `src/jarvis/tools/builtin/media.py` | Yes | Zero `sudo usermod` calls allowed |
| Task 5 | Task 6,7 | `Orchestrator` -> `TaskPlanner` -> `TaskManager` | Yes | Centralized flow |
| Task 6 | Task 7 | FastAPI Exception Handlers | Yes | Precise status codes (403, 409, 429) |
| Task 7 | Task 8 | `asyncio.to_thread` sync handler wrapping | Yes | Non-blocking execution |

Pre-flight scan complete: 0 conflicts found.
