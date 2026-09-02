# Current Architecture (Legacy + Initial Linux Modules)

## State Summary
The repository currently contains both legacy root-level execution modules (`run.py`, `api/server.py`, `tools/executor.py`, `task_engine/`, etc.) and the initial `src/jarvis` Linux-first foundational modules.

```text
OLD JARVIS (Root level)
run.py / api/server.py
 ├── Root API & custom HTTP server
 ├── Legacy ToolRegistry & ToolExecutor
 ├── task_engine / TaskManager
 ├── Voice pipeline & perception
 └── Legacy Security Policy

       +

NEW JARVIS (src/jarvis/)
src/jarvis/
 ├── app (Application lifecycle)
 ├── api (FastAPI app & schemas)
 ├── system (paths, process, distro, permissions)
 ├── tools (ToolExecutor gate, RiskLevel policy, builtin tools)
 ├── tasks (TaskPlan models & TaskManager routing)
 ├── config (Pydantic Settings & structured logging)
 └── scripts / doctor
```

## Known Architectural Debts
1. **Dual Execution Paths:** Legacy modules bypass `ToolExecutor` and invoke tool handlers directly.
2. **Duplicated Tool Registries:** `run.py` registers tools independently from `src/jarvis/tools/executor.py`.
3. **Unsanitized Subprocess Calls:** Legacy tools contain direct `subprocess.run(..., shell=True)` invocations.
4. **CLI Disconnect:** The `jarvis` entrypoint does not run the application lifecycle.
5. **Path Scatter:** Residual tools write to hardcoded `/tmp` paths rather than XDG standard directories.
