# Task 5 Brief: Remove arbitrary shell tool entirely

**Fixes issue:** #12 (arbitrary command still accessible via shlex.split)

## Problem

`tools/builtin/shell_exec.py` still exists. Even with `shell=False` and `shlex.split`, a user/LLM can pass `rm -rf /`, `curl malicious.url`, or `python -c "..."` as the command. The tool is fundamentally unsafe for an AI agent.

## Target

Delete `tools/builtin/shell_exec.py` entirely. Ensure no tool named `run_command` exists in the registry.

## Files to modify

### 1. DELETE `tools/builtin/shell_exec.py`

```bash
git rm tools/builtin/shell_exec.py
```

### 2. MODIFY `tools/__init__.py`

Remove any reference to `shell_exec` or `run_command` if present.

### 3. WRITE TEST `tests/security/test_no_arbitrary_shell.py`

```python
from pathlib import Path

def test_shell_exec_file_does_not_exist():
    """The arbitrary shell execution tool file must not exist."""
    assert not Path("tools/builtin/shell_exec.py").exists()

def test_no_run_command_in_registry():
    """No tool named 'run_command' may exist in the canonical registry."""
    from jarvis.app.application import Application
    app = Application()
    assert not app.registry.has("run_command")
    assert not app.registry.has("shell_exec")
```

## Execution steps

1. Write test `tests/security/test_no_arbitrary_shell.py`
2. Run: `PYTHONPATH=src pytest tests/security/test_no_arbitrary_shell.py` — expect failure on file existence
3. Delete `tools/builtin/shell_exec.py` and clean `tools/__init__.py`
4. Run test again — expect passes
5. Run: `PYTHONPATH=src pytest tests/security/` — all security tests pass
6. Commit: `git rm tools/builtin/shell_exec.py && git add -A && git commit -m "security(tools): remove arbitrary shell execution tool entirely"`
7. Write report to `/home/shanu/Desktop/jarvis-pc/.superpowers/sdd/2026-09-03-composition-root-plan/task-5-report.md`
