import pytest
from pathlib import Path
from jarvis.cli.doctor import run_doctor


def test_real_doctor_checks_xdg_write():
    report = run_doctor()
    assert "OK" in report
    assert "XDG Paths:" in report
    assert "0 errors" in report


def test_doctor_dependency_and_version_checks():
    report = run_doctor()
    assert "Python:" in report
    assert "Dependencies:" in report
    assert "fastapi" in report
    assert "uvicorn" in report
    assert "pydantic" in report
    assert "psutil" in report


def test_systemd_unit_no_user_directive():
    service_file = Path("deploy/systemd/jarvis.service")
    content = service_file.read_text()
    assert "User=" not in content, "User=%u should not be in user service file"
    assert "ExecStart=%h/.local/share/jarvis/venv/bin/jarvis run" in content


def test_installer_script_contents():
    install_script = Path("scripts/install.sh")
    content = install_script.read_text()
    assert "set -Eeuo pipefail" in content
    assert "uv" in content
    assert "venv" in content
    assert "doctor" in content
