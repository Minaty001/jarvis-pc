# Recovery & Checkpoints Architecture

## Step Checkpointing
Upon completion of every `TaskStep`, `DAGExecutor` writes a JSON checkpoint record to SQLite:
`INSERT OR REPLACE INTO checkpoints(task_id, step_id, data, saved_at)`

## Startup Recovery Algorithm
When JARVIS boots:
1. `CrashRecovery.recover()` queries non-terminal tasks from SQLite.
2. `RUNNING` or `RETRYING` tasks have in-flight uncheckpointed steps reset to `PENDING`.
3. Already checkpointed steps are marked `COMPLETED` and skipped during re-run (idempotency).
4. Task transitions to `READY` and resumes execution asynchronously without re-running completed side effects.
