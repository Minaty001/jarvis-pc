# JARVIS-PC Full Migration Plan

## Objectives
Transform JARVIS-PC into a single-path, security-controlled, service-oriented Python application where `src/jarvis` is the sole source of truth and all side-effecting operations flow through a single `ToolExecutor` gate (`TaskManager -> ToolExecutor -> Policy -> Tool`).

## Phase Summary
- **Phase 0:** Freeze baseline (`refactor/complete-linux-migration` branch, `pre-complete-migration` tag, architecture docs).
- **Phase 1-3:** `src/jarvis` single source of truth, canonical `ToolDefinition`, single `ToolRegistry`.
- **Phase 4-7:** Single `ToolExecutor` gate, capability authorization (`ExecutionContext`), server-side HMAC confirmation, rate limiting & auditing.
- **Phase 8-9:** Eliminate `TaskManager` `.handler()` bypass, migrate `task_engine/` into `src/jarvis/tasks/`.
- **Phase 10-13:** Remove arbitrary shell execution, safe `ProcessManager`, allowlist app control, remove runtime `sudo` from camera.
- **Phase 14-16:** Migrate orchestrator to planner, make `Application` lifecycle authoritative (`start()`, `stop()`), add startup rollback.
- **Phase 17-21:** Migrate API to FastAPI/Uvicorn, enforce remote authentication, error status mapping, `to_thread` sync adapter, async SSE streaming.
- **Phase 22-27:** Self-contained CLI (`jarvis run`, `jarvis doctor`, `jarvis status`), real Linux doctor diagnostic, systemd user service, installer script (`set -Eeuo pipefail`), voice lifecycle cleanup, UI readiness signal.
- **Phase 28-35:** Remove legacy `run.py` & `api/server.py`, reproducible `uv.lock`, full security & integration test suite, Linux matrix verification, performance optimization, CI/CD production gate.
