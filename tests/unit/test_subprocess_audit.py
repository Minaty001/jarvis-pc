from pathlib import Path


def test_no_shell_true_in_src():
    src_dir = Path("src/jarvis")
    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text()
        assert "shell=True" not in content, f"Forbidden shell=True found in {py_file}"
