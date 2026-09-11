"""Tests for Linux Software Package Management, Software Installation & Desktop Application Discovery."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.system.packages import (
    detect_primary_package_manager,
    find_application_binary,
    get_available_package_managers,
    get_package_info,
    is_package_installed,
    list_desktop_applications,
    list_installed_packages,
    search_packages,
)
from jarvis.tools.builtin.applications import (
    ApplicationError,
    check_installed_package,
    get_system_package_manager_status,
    list_installed_applications,
    open_application,
    search_linux_software,
)


def test_package_manager_detection():
    with patch("shutil.which") as mock_which:
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}" if cmd in ("apt-get", "apt", "flatpak") else None
        mgrs = get_available_package_managers()
        assert "apt-get" in mgrs
        assert "apt" in mgrs
        assert "flatpak" in mgrs

        primary = detect_primary_package_manager()
        assert primary == "apt-get"


def test_is_package_installed():
    # 1. Binary found in PATH
    with patch("shutil.which", return_value="/usr/bin/curl"):
        assert is_package_installed("curl") is True

    # 2. Binary not in PATH, but dpkg installed
    with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
        mock_which.side_effect = lambda cmd: "/usr/bin/dpkg-query" if cmd == "dpkg-query" else None
        res_mock = MagicMock()
        res_mock.stdout = "install ok installed"
        res_mock.returncode = 0
        mock_run.return_value = res_mock

        assert is_package_installed("libssl-dev") is True


def test_search_and_list_packages():
    # Test search with apt-cache output
    apt_search_out = "htop - interactive process viewer\ngit - fast scalable distributed revision control system"
    with patch("shutil.which", return_value="/usr/bin/apt-cache"), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=apt_search_out, returncode=0)
        res = search_packages("htop")
        assert len(res) == 2
        assert res[0]["name"] == "htop"
        assert "process viewer" in res[0]["description"]

    # Test list installed packages
    dpkg_list_out = "curl\ngit\npython3\n"
    with patch("shutil.which", return_value="/usr/bin/dpkg-query"), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=dpkg_list_out, returncode=0)
        pkgs = list_installed_packages()
        assert "git" in pkgs
        assert "python3" in pkgs


def test_desktop_applications_discovery(tmp_path):
    desktop_file = tmp_path / "code.desktop"
    desktop_file.write_text(
        "[Desktop Entry]\n"
        "Name=Visual Studio Code\n"
        "Exec=code %F\n"
        "Icon=vscode\n"
        "Type=Application\n",
        encoding="utf-8",
    )

    with patch("jarvis.system.packages._DESKTOP_DIRS", [tmp_path]):
        apps = list_desktop_applications()
        assert len(apps) == 1
        assert apps[0]["name"] == "Visual Studio Code"
        assert apps[0]["exec"] == "code"

        with patch("shutil.which", return_value="/usr/bin/code"):
            bin_path = find_application_binary("visual studio code")
            assert bin_path in ("code", "/usr/bin/code")


@pytest.mark.asyncio
async def test_builtin_package_tools():
    # 1. Check installed tool
    with patch("jarvis.tools.builtin.applications.is_package_installed", return_value=True), \
         patch("jarvis.tools.builtin.applications.get_package_info", return_value={"version": "1.0.0", "description": "Core utility"}):
        res = await check_installed_package("htop")
        assert "INSTALLED" in res
        assert "1.0.0" in res

    # 2. Search software tool
    with patch("jarvis.tools.builtin.applications.search_packages", return_value=[{"name": "vlc", "description": "Media player"}]), \
         patch("jarvis.tools.builtin.applications.detect_primary_package_manager", return_value="apt"):
        res = await search_linux_software("vlc")
        assert "vlc" in res
        assert "Media player" in res

    # 3. Status tool
    with patch("jarvis.tools.builtin.applications.get_available_package_managers", return_value=["apt", "flatpak"]), \
         patch("jarvis.tools.builtin.applications.detect_primary_package_manager", return_value="apt"):
        res = await get_system_package_manager_status()
        assert "APT" in res
        assert "flatpak" in res


@pytest.mark.asyncio
async def test_open_application_routing():
    # Allowed map app
    with patch("jarvis.tools.builtin.applications.run_process") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        res = await open_application("firefox")
        assert res.returncode == 0
        mock_run.assert_called_with(["firefox"], timeout=10.0)

    # Dynamic lookup app
    with patch("jarvis.tools.builtin.applications.find_application_binary", return_value="/usr/bin/vlc"), \
         patch("jarvis.tools.builtin.applications.run_process") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        res = await open_application("vlc")
        assert res.returncode == 0

    # Non-existent app
    with patch("jarvis.tools.builtin.applications.find_application_binary", return_value=None):
        with pytest.raises(ApplicationError):
            await open_application("non_existent_fake_app_xyz")


def test_cli_pkg_and_apps(capsys):
    from jarvis.cli.main import run_cli

    # CLI pkg check
    with patch("jarvis.system.packages.is_package_installed", return_value=True), \
         patch("jarvis.system.packages.get_package_info", return_value={"version": "2.40", "description": "Git VCS"}):
        code = run_cli(["pkg", "check", "git"])
        assert code == 0
        out = capsys.readouterr().out
        assert "Package:     git" in out
        assert "INSTALLED" in out

    # CLI apps list
    with patch("jarvis.system.packages.list_desktop_applications", return_value=[{"name": "GIMP", "id": "gimp", "exec": "gimp"}]):
        code = run_cli(["apps", "list"])
        assert code == 0
        out = capsys.readouterr().out
        assert "GIMP" in out
