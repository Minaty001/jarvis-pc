import os
from pathlib import Path


def test_systemd_unit_validity():
    unit_path = Path("deploy/systemd/jarvis.service")
    assert unit_path.exists()
    content = unit_path.read_text()
    assert "[Unit]" in content
    assert "[Service]" in content
    assert "[Install]" in content
    assert "ExecStart=" in content
    assert "NoNewPrivileges=true" in content
    assert "ProtectSystem=strict" in content
    assert "ProtectHome=read-only" in content
    assert "PrivateTmp=true" in content
    assert "RestrictSUIDSGID=true" in content
    assert "ReadWritePaths=%h/.config/jarvis" in content
    assert "ReadWritePaths=%h/.local/share/jarvis" in content
    assert "ReadWritePaths=%h/.local/state/jarvis" in content
    assert "ReadWritePaths=%h/.cache/jarvis" in content


def test_install_script_validity():
    install_script = Path("scripts/install.sh")
    assert install_script.exists()
    assert os.access(install_script, os.X_OK)
    content = install_script.read_text()
    assert "jarvis.service" in content


def test_uninstall_script_validity():
    uninstall_script = Path("scripts/uninstall.sh")
    assert uninstall_script.exists()
    assert os.access(uninstall_script, os.X_OK)
    content = uninstall_script.read_text()
    assert "jarvis.service" in content
