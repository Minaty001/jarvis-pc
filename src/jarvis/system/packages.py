"""Linux Package Management, Software Installation & Desktop Application Discovery for JARVIS PC."""

from __future__ import annotations

import glob
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess  # nosec B404
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Known desktop search directories
_DESKTOP_DIRS = [
    Path.home() / ".local" / "share" / "applications",
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
    Path("/var/lib/flatpak/exports/share/applications"),
    Path.home() / ".local" / "share" / "flatpak" / "exports" / "share" / "applications",
    Path("/var/lib/snapd/desktop/applications"),
]


def get_available_package_managers() -> List[str]:
    """Return all package managers present on this Linux system."""
    managers = []
    for mgr in ("apt-get", "apt", "pacman", "dnf", "zypper", "apk", "flatpak", "snap", "pip", "uv"):
        if shutil.which(mgr):
            managers.append(mgr)
    return managers


def detect_primary_package_manager() -> str:
    """Detect the default system package manager based on distro and binaries."""
    for primary in ("apt-get", "pacman", "dnf", "zypper", "apk"):
        if shutil.which(primary):
            return primary
    if shutil.which("flatpak"):
        return "flatpak"
    if shutil.which("snap"):
        return "snap"
    return "unknown"


def is_package_installed(pkg_name: str) -> bool:
    """Check if a software package is installed on the host system."""
    clean_name = pkg_name.strip().lower()

    # 1. Quick binary lookup
    if shutil.which(clean_name):
        return True

    # 2. Native package manager queries
    try:
        if shutil.which("dpkg-query"):
            res = subprocess.run(  # nosec B603
                ["dpkg-query", "-W", "-f=${Status}", clean_name],
                capture_output=True,
                text=True,
                timeout=4.0,
                check=False,
            )
            if "install ok installed" in res.stdout:
                return True
        elif shutil.which("pacman"):
            res = subprocess.run(  # nosec B603
                ["pacman", "-Q", clean_name],
                capture_output=True,
                text=True,
                timeout=4.0,
                check=False,
            )
            if res.returncode == 0:
                return True
        elif shutil.which("rpm"):
            res = subprocess.run(  # nosec B603
                ["rpm", "-q", clean_name],
                capture_output=True,
                text=True,
                timeout=4.0,
                check=False,
            )
            if res.returncode == 0:
                return True
    except Exception as exc:
        logger.debug("Error checking package status for %s: %s", clean_name, exc)

    # 3. Flatpak lookup
    if shutil.which("flatpak"):
        try:
            res = subprocess.run(  # nosec B603
                ["flatpak", "info", clean_name],
                capture_output=True,
                text=True,
                timeout=4.0,
                check=False,
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass

    # 4. Snap lookup
    if shutil.which("snap"):
        try:
            res = subprocess.run(  # nosec B603
                ["snap", "list", clean_name],
                capture_output=True,
                text=True,
                timeout=4.0,
                check=False,
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass

    return False


def search_packages(query: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Search for available software packages across system repositories."""
    clean_query = query.strip()
    results: List[Dict[str, Any]] = []

    if shutil.which("apt-cache"):
        try:
            res = subprocess.run(  # nosec B603
                ["apt-cache", "search", clean_query],
                capture_output=True,
                text=True,
                timeout=6.0,
                check=False,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines()[:limit]:
                    if " - " in line:
                        pname, pdesc = line.split(" - ", 1)
                        results.append({
                            "name": pname.strip(),
                            "description": pdesc.strip(),
                            "manager": "apt",
                        })
        except Exception as exc:
            logger.debug("apt-cache search error: %s", exc)

    elif shutil.which("pacman"):
        try:
            res = subprocess.run(  # nosec B603
                ["pacman", "-Ss", clean_query],
                capture_output=True,
                text=True,
                timeout=6.0,
                check=False,
            )
            if res.returncode == 0:
                lines = res.stdout.splitlines()
                for i in range(0, len(lines) - 1, 2):
                    pname = lines[i].split("/")[1].split()[0] if "/" in lines[i] else lines[i].split()[0]
                    pdesc = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    results.append({"name": pname, "description": pdesc, "manager": "pacman"})
                    if len(results) >= limit:
                        break
        except Exception as exc:
            logger.debug("pacman search error: %s", exc)

    elif shutil.which("dnf"):
        try:
            res = subprocess.run(  # nosec B603
                ["dnf", "search", "-q", clean_query],
                capture_output=True,
                text=True,
                timeout=6.0,
                check=False,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines()[:limit]:
                    if " : " in line:
                        pname, pdesc = line.split(" : ", 1)
                        results.append({"name": pname.strip(), "description": pdesc.strip(), "manager": "dnf"})
        except Exception as exc:
            logger.debug("dnf search error: %s", exc)

    return results


def list_installed_packages(filter_query: str = "", limit: int = 50) -> List[str]:
    """List installed packages matching optional filter."""
    pkgs: List[str] = []
    clean_filter = filter_query.strip().lower()

    if shutil.which("dpkg-query"):
        try:
            res = subprocess.run(  # nosec B603
                ["dpkg-query", "-W", "-f=${Package}\\n"],
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    name = line.strip()
                    if not clean_filter or clean_filter in name.lower():
                        pkgs.append(name)
                        if len(pkgs) >= limit:
                            break
        except Exception:
            pass

    elif shutil.which("pacman"):
        try:
            res = subprocess.run(  # nosec B603
                ["pacman", "-Qq"],
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    name = line.strip()
                    if not clean_filter or clean_filter in name.lower():
                        pkgs.append(name)
                        if len(pkgs) >= limit:
                            break
        except Exception:
            pass

    elif shutil.which("rpm"):
        try:
            res = subprocess.run(  # nosec B603
                ["rpm", "-qa", "--qf", "%{NAME}\\n"],
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    name = line.strip()
                    if not clean_filter or clean_filter in name.lower():
                        pkgs.append(name)
                        if len(pkgs) >= limit:
                            break
        except Exception:
            pass

    return pkgs


def get_package_info(pkg_name: str) -> Dict[str, Any]:
    """Retrieve detailed metadata and version for an installed or repository package."""
    clean_name = pkg_name.strip()
    info: Dict[str, Any] = {
        "package": clean_name,
        "installed": is_package_installed(clean_name),
        "version": "unknown",
        "description": "No description available",
    }

    if shutil.which("dpkg-query"):
        try:
            res = subprocess.run(  # nosec B603
                ["dpkg-query", "-W", "-f=${Version}///${Section}///${Description}", clean_name],
                capture_output=True,
                text=True,
                timeout=4.0,
                check=False,
            )
            if res.returncode == 0 and "///" in res.stdout:
                parts = res.stdout.split("///")
                info["version"] = parts[0].strip()
                if len(parts) >= 3:
                    info["description"] = parts[2].splitlines()[0].strip()
        except Exception:
            pass

    elif shutil.which("pacman"):
        try:
            res = subprocess.run(  # nosec B603
                ["pacman", "-Qi", clean_name],
                capture_output=True,
                text=True,
                timeout=4.0,
                check=False,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if line.startswith("Version"):
                        info["version"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Description"):
                        info["description"] = line.split(":", 1)[1].strip()
        except Exception:
            pass

    return info


def list_desktop_applications() -> List[Dict[str, Any]]:
    """Scan Linux desktop application directories to find all installed GUI programs."""
    apps: Dict[str, Dict[str, Any]] = {}

    for ddir in _DESKTOP_DIRS:
        if not ddir.exists():
            continue

        for desktop_file in ddir.glob("*.desktop"):
            try:
                name = ""
                exec_cmd = ""
                icon = ""
                nodisplay = False

                for line in desktop_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line.startswith("Name=") and not name:
                        name = line.split("=", 1)[1].strip()
                    elif line.startswith("Exec=") and not exec_cmd:
                        raw_exec = line.split("=", 1)[1].strip()
                        # Strip field codes like %u, %U, %f, %F
                        exec_cmd = re.sub(r"%[a-zA-Z]", "", raw_exec).strip()
                    elif line.startswith("Icon=") and not icon:
                        icon = line.split("=", 1)[1].strip()
                    elif line.startswith("NoDisplay=true"):
                        nodisplay = True

                if name and exec_cmd and not nodisplay:
                    app_id = desktop_file.stem
                    if app_id not in apps:
                        apps[app_id] = {
                            "id": app_id,
                            "name": name,
                            "exec": exec_cmd,
                            "icon": icon,
                            "desktop_file": str(desktop_file),
                        }
            except Exception:
                continue

    return sorted(list(apps.values()), key=lambda x: x["name"].lower())


def find_application_binary(app_name: str) -> Optional[str]:
    """Find executable or desktop command for an application name."""
    clean_name = app_name.strip().lower()

    # 1. Direct which lookup
    which_bin = shutil.which(clean_name)
    if which_bin:
        return which_bin

    # 2. Desktop applications lookup
    for app in list_desktop_applications():
        if clean_name == app["id"].lower() or clean_name == app["name"].lower() or clean_name in app["name"].lower():
            # Return binary name from exec
            cmd = app["exec"].split()[0]
            if shutil.which(cmd):
                return cmd

    return None
