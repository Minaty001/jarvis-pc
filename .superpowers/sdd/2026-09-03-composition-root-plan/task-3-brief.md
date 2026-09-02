# Task 3 Brief: Make ExecutionContext mandatory & fix API context creation

**Fixes issue:** #9 (capability check bypassable when context=None)

**Depends on:** Task 1 (API now creates ExecutionContext per request)

## Problem

`ToolExecutor.execute()` has `context: Optional[ExecutionContext] = None`. When context is None, the capability check `if context and tool.capabilities:` is skipped entirely. The API currently calls executor without creating a context.

## Target

- `context` parameter in `ToolExecutor.execute()` becomes **mandatory** (not Optional).
- Any caller without a context gets a `TypeError`.
- API creates `ExecutionContext` per request (should already be done in Task 1's `app.py` rewrite).

## Files to modify

### 1. MODIFY `src/jarvis/tools/executor.py`

Change signature of `execute()`:
```python
async def execute(
    self,
    tool_name: str | None = None,
    *args: Any,
    context: ExecutionContext,  # MANDATORY, not Optional
    ...
) -> Any:
```

Remove the `if context` guard from capability check:
```python
if tool.capabilities:
    if not (tool.capabilities <= context.permissions):
        raise ToolDenied(...)
```

Change `session_id = context.session_id if context else ""` to just `session_id = context.session_id`.

Change `request_id = context.request_id if context else "none"` to `request_id = context.request_id`.

### 2. MODIFY `src/jarvis/tasks/manager.py`

Make `context` mandatory in `execute_step`:
```python
async def execute_step(self, step: TaskStep, context: ExecutionContext, ...) -> Any:
```

### 3. WRITE TEST `tests/security/test_context_mandatory.py`

```python
import pytest
from jarvis.tools.executor import ToolExecutor
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel
from jarvis.cognitive.context import ExecutionContext


@pytest.mark.asyncio
async def test_executor_rejects_missing_context():
    """execute() must raise TypeError when context is not provided."""
    registry = ToolRegistry()
    async def dummy(): return "ok"
    registry.register(ToolDefinition("test_tool", RiskLevel.SAFE, frozenset(), dummy))
    executor = ToolExecutor(registry)
    with pytest.raises(TypeError):
        await executor.execute("test_tool", arguments={})


@pytest.mark.asyncio
async def test_capabilities_always_enforced():
    """Capabilities must be checked even for seemingly simple calls."""
    registry = ToolRegistry()
    async def dummy(): return "ok"
    registry.register(ToolDefinition("write_file", RiskLevel.SAFE, frozenset({"filesystem.write"}), dummy))
    executor = ToolExecutor(registry)
    ctx = ExecutionContext("s1", "t1", "u1", "r1", permissions=frozenset())
    from jarvis.tools.executor import ToolDenied
    with pytest.raises(ToolDenied):
        await executor.execute("write_file", context=ctx)
```

## Execution steps

1. Write test `tests/security/test_context_mandatory.py`
2. Run: `PYTHONPATH=src pytest tests/security/test_context_mandatory.py` — expect failures
3. Modify `src/jarvis/tools/executor.py` and `src/jarvis/tasks/manager.py`
4. Run test again — expect passes
5. Run broader security suite: `PYTHONPATH=src pytest tests/security/`
6. Fix any test regressions (existing tests that call `execute()` without context need updating — add a context to them)
7. Commit: `git add -A && git commit -m "security(executor): make ExecutionContext mandatory, reject unauthenticated tool execution"`
8. Write report to `/home/shanu/Desktop/jarvis-pc/.superpowers/sdd/2026-09-03-composition-root-plan/task-3-report.md`
