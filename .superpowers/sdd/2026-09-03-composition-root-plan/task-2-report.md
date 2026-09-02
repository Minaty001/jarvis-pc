# Task 2 Report: CLI Persistent Lifecycle with Signal Handling

- **Status**: DONE
- **Commit Hash**: `65b51d1`

## Summary of Changes
1. Added unit tests in `tests/unit/test_cli_lifecycle.py` to verify `run_until_stopped()` and `request_stop()`.
2. Updated `src/jarvis/cli/main.py` so `parsed_args.subcommand == "run"` invokes `asyncio.run(application.run_until_stopped())`.
3. Updated CLI unit/integration tests (`test_cli.py`, `test_run_entrypoint.py`) to pass a mock `Application` where appropriate.

## Verification
- Test command: `PYTHONPATH=src pytest tests/unit/test_cli_lifecycle.py tests/unit/test_cli.py tests/integration/test_run_entrypoint.py`
- Result: 8 passed in 5.47s.
