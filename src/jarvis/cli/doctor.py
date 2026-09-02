from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from jarvis.system.distro import detect_distribution
from jarvis.system.paths import get_app_paths


def _check_xdg_path(path: Path) -> tuple[str, bool]:
    """Perform empirical read/write file check on an XDG directory."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".doctor_test"
        test_content = "jarvis_doctor_check"
        test_file.write_text(test_content)
        read_back = test_file.read_text()
        if test_file.exists():
            test_file.unlink()
        if read_back == test_content:
            return "OK", True
        return "FAIL (readback mismatch)", False
    except Exception as exc:
        return f"FAIL ({exc})", False


def run_doctor() -> str:
    errors = 0
    lines = [
        "JARVIS Linux Doctor",
        "-------------------",
        "",
        "OS:",
        f"  {detect_distribution().pretty_name}",
        "",
        "Python:",
    ]

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 12):
        lines.append(f"  {py_ver}      OK")
    else:
        lines.append(f"  {py_ver}      FAIL (Python >= 3.12 required)")
        errors += 1

    lines.extend([
        "",
        "CPU:",
        f"  {os.uname().machine}      OK",
        "",
        "Dependencies:",
    ])

    dependencies = ["fastapi", "uvicorn", "pydantic", "psutil"]
    for dep in dependencies:
        try:
            importlib.import_module(dep)
            lines.append(f"  {dep:<10} OK")
        except ImportError:
            lines.append(f"  {dep:<10} FAIL (missing)")
            errors += 1

    lines.extend([
        "",
        "XDG Paths:",
    ])
    paths = get_app_paths()
    path_entries = [
        ("CONFIG", paths.config),
        ("DATA", paths.data),
        ("STATE", paths.state),
        ("CACHE", paths.cache),
        ("RUNTIME", paths.runtime),
    ]

    for name, path in path_entries:
        status_str, ok = _check_xdg_path(path)
        lines.append(f"  {name:<7}({path})      {status_str}")
        if not ok:
            errors += 1

    lines.extend([
        "",
        "Result:",
        f"  {errors} errors",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    report = run_doctor()
    print(report)
    sys.exit(0 if "0 errors" in report else 1)
