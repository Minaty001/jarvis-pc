import ast
from pathlib import Path


def test_single_handler_invocation_site():
    src_dir = Path("src/jarvis")
    allowed = Path("src/jarvis/tools/executor.py").resolve()

    violations = []
    for py_file in src_dir.rglob("*.py"):
        if py_file.resolve() == allowed:
            continue
        content = py_file.read_text()
        if ".handler(" in content:
            violations.append(str(py_file))

    assert not violations, f"Direct .handler() call found outside ToolExecutor in: {violations}"
