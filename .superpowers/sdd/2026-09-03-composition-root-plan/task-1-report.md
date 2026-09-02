# Task 1 Report: Composition Root

## Work Completed
1. Created `tests/unit/test_composition_root.py` to enforce that `Application` and `app.py` are the only places that instantiate `ToolExecutor`.
2. Created `src/jarvis/tools/builtin/registry_init.py` with `register_all_builtins()` to register all builtin tools. Removed an unused `xdg_data_home` import.
3. Rewrote `src/jarvis/app/application.py` to construct `ToolRegistry`, call `register_all_builtins`, construct `ToolExecutor`, and assign them as properties.
4. Rewrote `src/jarvis/api/app.py` to use a `create_api_app` factory that takes a `ToolExecutor`.
5. Modified `task_engine/manager.py` to remove the module-level instance and `_default_step_runner`, instead relying on an injected `ToolExecutor` and a bound `_step_runner` method.
6. Fixed integration and lifecycle tests (`test_api.py`, `test_api_error_mapping.py`, `test_application_lifecycle.py`, `test_hardened_security.py`, `test_task_manager_single_path.py`) to properly inject dependencies following the refactor.
7. Successfully executed the broader test suite (`pytest tests/unit tests/security tests/integration tests/architecture`) with 102 passing tests.
8. Committed changes with the required message.

## Outcome
The application now acts as the true composition root, owning the `ToolRegistry` and `ToolExecutor`, which is successfully injected into `TaskManager` and the API. Issue #5, #7, and #19 have been resolved.
