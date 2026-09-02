import ast
from pathlib import Path


def test_single_handler_invocation_site():
    search_dirs = [Path("src/jarvis"), Path("task_engine")]
    allowed = {
        Path("src/jarvis/tools/executor.py").resolve(),
        Path("tools/executor.py").resolve(),
    }

    violations = []
    for sdir in search_dirs:
        if not sdir.exists():
            continue
        for py_file in sdir.rglob("*.py"):
            if py_file.resolve() in allowed:
                continue
            content = py_file.read_text()
            if ".handler(" in content:
                violations.append(str(py_file))

    assert not violations, f"Direct .handler() call found outside ToolExecutor in: {violations}"

