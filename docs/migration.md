# Migration Strategy & Roadmap

## Migration Strategy: Incrementally Migrate, Verify, and Delete

Instead of a big-bang rewrite, legacy components are migrated step-by-step into `src/jarvis/`:

```text
Legacy Implementation
        ↓
Migrate to src/jarvis/
        ↓
Add Unit & Security Tests
        ↓
Switch Call Sites
        ↓
Remove Legacy Files
```

## Phase Sequence

1. **Phase 0:** Freeze repository, create tag `pre-linux-migration` and branch `refactor/linux-core`.
2. **Phase 1-3:** Package structure consolidation, CLI entrypoint repair (`jarvis run`, `jarvis doctor`), move doctor to `src/jarvis/cli/doctor.py`.
3. **Phase 4-7:** Dependency locks (`pyproject.toml` + `uv.lock`), Linux process runner (`src/jarvis/system/process.py`), replace `subprocess.run(shell=True)` and remove arbitrary shell tools.
4. **Phase 8-12:** Canonical `ToolDefinition`, `ToolRegistry`, single `ToolExecutor` gate, server-side confirmation, update `TaskManager` to route all execution through `ToolExecutor`.
5. **Phase 13-17:** Consolidate `task_engine/` into `src/jarvis/tasks/`, introduce `ExecutionContext`, update `cognitive` orchestrator & planner, migrate API to FastAPI.
6. **Phase 18-28:** API limits, SSE streaming, Application lifecycle & voice shutdown, camera permission check without `sudo`, systemd user service & installer.
7. **Phase 29-34:** Database repository layer, full test matrix, CI pipeline, dead code removal, performance benchmarks, release tag.
