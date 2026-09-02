import sys
from pathlib import Path
from unittest.mock import patch

# Ensure repository root is in sys.path
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.doctor import run_doctor
from jarvis.__main__ import main


def test_run_doctor():
    report = run_doctor()
    assert "OS:" in report
    assert "Python:" in report
    assert "XDG Paths:" in report
    assert "0 errors" in report


def test_main_doctor(capsys):
    with patch.object(sys, "argv", ["jarvis", "doctor"]):
        main()
    captured = capsys.readouterr()
    assert "JARVIS Linux Doctor" in captured.out
    assert "0 errors" in captured.out


def test_main_default(capsys):
    with patch.object(sys, "argv", ["jarvis"]):
        main()
    captured = capsys.readouterr()
    assert "JARVIS CLI v1.0.0 (Linux)" in captured.out
