import ast
from pathlib import Path


def test_new_architecture_does_not_import_legacy():
    src_dir = Path("src/jarvis")
    legacy_modules = {"task_engine", "api.server"}

    forbidden = []
    for py_file in src_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name.startswith(m) for m in legacy_modules):
                        forbidden.append((str(py_file), alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and any(
                    node.module.startswith(m) for m in legacy_modules
                ):
                    forbidden.append((str(py_file), node.module))

    assert not forbidden, f"Forbidden legacy imports found in src/jarvis: {forbidden}"
