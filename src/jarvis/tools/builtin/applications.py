"""Builtin tools for Linux Software Package Management, Application Execution & Desktop Program Discovery."""

from __future__ import annotations

import asyncio
import logging
import shutil
from typing import Any, Dict, List

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
from jarvis.system.process import ProcessResult, run_process

logger = logging.getLogger(__name__)

ALLOWED_APPLICATIONS: dict[str, tuple[str, ...]] = {
    "firefox": ("firefox",),
    "chrome": ("google-chrome",),
    "chromium": ("chromium",),
    "terminal": ("x-terminal-emulator",),
    "code": ("code",),
    "cursor": ("cursor",),
    "vlc": ("vlc",),
    "spotify": ("spotify",),
    "discord": ("discord",),
    "nautilus": ("nautilus",),
    "files": ("nautilus",),
    "gedit": ("gedit",),
    "calculator": ("gnome-calculator",),
    "calc": ("gnome-calculator",),
    "settings": ("gnome-control-center",),
}

_ALLOWED_URL_SCHEMES = ("http", "https")


class ApplicationError(RuntimeError):
    pass


async def open_application(name: str) -> ProcessResult:
    """Launch a desktop application or system utility on Linux."""
    key = name.strip().lower()

    # 1. Check known applications mapping
    command = ALLOWED_APPLICATIONS.get(key)
    if command is not None:
        return await run_process(list(command), timeout=10.0)

    # 2. Check dynamic desktop application database or path
    bin_path = find_application_binary(key)
    if bin_path:
        return await run_process([bin_path], timeout=10.0)

    raise ApplicationError(f"application {name!r} is not allowed or not found on this system")


async def open_url(url: str) -> ProcessResult:
    """Open a web URL using xdg-open."""
    scheme = url.strip().split(":", 1)[0].lower()
    if scheme not in _ALLOWED_URL_SCHEMES:
        raise ApplicationError(f"unsupported URL scheme {scheme!r}")
    return await run_process(["xdg-open", url.strip()], timeout=10.0)


async def list_installed_applications() -> str:
    """List all installed desktop applications and GUI programs found in application paths."""
    apps = await asyncio.to_thread(list_desktop_applications)
    if not apps:
        return "No desktop GUI applications discovered in standard application directories."

    lines = [f"JARVIS Installed Desktop Applications ({len(apps)} programs):"]
    lines.append("=" * 75)
    for a in apps:
        lines.append(f"• {a['name']:<30} | ID: {a['id']:<20} | Command: {a['exec']}")
    lines.append("=" * 75)

    return "\n".join(lines)


async def check_installed_package(package_name: str) -> str:
    """Check whether a Linux software package is currently installed on the host."""
    clean_name = package_name.strip()
    installed = await asyncio.to_thread(is_package_installed, clean_name)
    info = await asyncio.to_thread(get_package_info, clean_name)

    if installed:
        return (
            f"Software Package '{clean_name}': INSTALLED\n"
            f"• Version:     {info.get('version', 'unknown')}\n"
            f"• Description: {info.get('description', 'N/A')}"
        )
    return (
        f"Software Package '{clean_name}': NOT INSTALLED\n"
        f"• Status: Available in repositories or external package managers."
    )


async def search_linux_software(query: str) -> str:
    """Search for available software packages across Linux package repositories."""
    results = await asyncio.to_thread(search_packages, query, 12)
    if not results:
        return f"No software packages matching query '{query}' were found in system repositories."

    mgr = detect_primary_package_manager()
    lines = [f"Software Packages for '{query}' [{mgr.upper()}]:"]
    lines.append("=" * 75)
    for r in results:
        lines.append(f"• {r['name']:<25} | {r.get('description', '')[:45]}")
    lines.append("=" * 75)

    return "\n".join(lines)


async def get_system_package_manager_status() -> str:
    """Inspect the primary Linux package manager, available package backends, and system distro."""
    managers = get_available_package_managers()
    primary = detect_primary_package_manager()

    return (
        f"Linux Package Management Subsystem:\n"
        f"• Primary Manager:    {primary.upper()}\n"
        f"• Available Backends: {', '.join(managers) if managers else 'None'}\n"
        f"• Package Installation Ready: {'YES' if primary != 'unknown' else 'NO'}"
    )
