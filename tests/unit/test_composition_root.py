"""Verify Application is the single composition root for the full object graph."""
import ast
import pytest
from pathlib import Path


def test_no_standalone_executor_construction():
    """No src/jarvis file outside application.py and app.py may construct ToolExecutor()."""
    src = Path("src/jarvis")
    # app.py has a backward-compat shim, allow it
    allowed = {"application.py", "app.py"}
    violations = []
    for py in src.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        if py.name in allowed:
            continue
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name == "ToolExecutor":
                    violations.append(f"{py.relative_to(src)}:{node.lineno}")
    assert not violations, f"ToolExecutor() constructed outside Application: {violations}"


def test_application_creates_full_graph():
    from jarvis.app.application import Application
    app = Application()
    assert app.registry is not None
    assert app.executor is not None
    assert app.executor.registry is app.registry
    assert len(app.registry.list()) > 0, "Registry must have tools registered"


def test_task_manager_no_inline_executor():
    """task_engine.manager.TaskManager must not construct ToolExecutor() inline."""
    src = Path("task_engine/manager.py")
    content = src.read_text()
    assert "ToolExecutor()" not in content, "TaskManager must not construct ToolExecutor()"
