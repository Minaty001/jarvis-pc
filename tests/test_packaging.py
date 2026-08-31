"""Slice 6 test: packaging — desktop file valid, install_user writes files."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ui import install_desktop


def test_packaging():
    # desktop file must validate
    from subprocess import run
    r = run(["desktop-file-validate", os.path.join(ROOT, "ui", "jarvis.desktop")],
            capture_output=True, text=True)
    assert r.returncode == 0, f"desktop-file-validate failed: {r.stderr}"

    # launcher exists + executable
    launcher = os.path.join(ROOT, "bin", "jarvis-ui")
    assert os.path.exists(launcher)
    assert os.access(launcher, os.X_OK), "jarvis-ui launcher not executable"

    # install_user writes into ~/.local
    res = install_desktop.install_user()
    assert os.path.exists(res["desktop"]), "desktop not installed"
    assert os.path.exists(res["launcher"]), "launcher not installed"
    assert os.access(res["launcher"], os.X_OK), "installed launcher not executable"
    assert "autostart" in res and os.path.exists(res["autostart"]), "autostart not installed"
    print("OK packaging: desktop valid, files installed to", os.path.dirname(res["desktop"]))


if __name__ == "__main__":
    test_packaging()
    print("SLICE 6 PASS")
