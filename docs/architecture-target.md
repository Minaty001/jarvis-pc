# Target Architecture for JARVIS-PC

## Consolidated Target Topology

```text
                    JARVIS-PC
                        │
               ┌────────┴────────┐
               │   Application   │
               └────────┬────────┘
                        │
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
      API             Voice             CLI
       │                │                │
       └────────────────┼────────────────┘
                        ▼
                  Orchestrator
                        ▼
                     Planner
                        ▼
                   TaskManager
                        ▼
                  ToolExecutor (Single Execution Gate)
                        ▼
             Authorization/Policy
                        ▼
             Structured Linux Tools
                        ▼
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
      Filesystem      Process       Desktop
```

## Key Architectural Principles

1. **Single Execution Gate:** No module other than `ToolExecutor` (`src/jarvis/tools/executor.py`) may directly invoke a side-effecting or privileged tool handler.
2. **`src/jarvis` as Sole Source of Truth:** All legacy root-level execution code (`run.py`, `api/server.py`, `task_engine/`) will be systematically migrated into `src/jarvis/` and deleted.
3. **No Arbitrary Shell:** No general-purpose `run_shell` or `shell=True` capability. All system actions use structured arguments and allowlist application control via `src/jarvis/system/process.py`.
4. **XDG Standard Compliance:** All user configuration, data, state, cache, and runtime files use `AppPaths` (`$XDG_CONFIG_HOME`, `$XDG_DATA_HOME`, `$XDG_STATE_HOME`, `$XDG_CACHE_HOME`, `$XDG_RUNTIME_DIR`).
5. **Central Application Lifecycle:** `Application.start()` and `Application.stop()` in `src/jarvis/app/application.py` manage subsystem startup and clean shutdown (Voice, API, Scheduler, DB).
