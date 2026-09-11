"""JARVIS system package."""

from __future__ import annotations

from jarvis.system.distro import LinuxDistribution, detect_distribution
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
from jarvis.system.paths import AppPaths, get_app_paths, initialize_paths
from jarvis.system.process import ProcessResult, run_process

__all__ = [
    "LinuxDistribution",
    "detect_distribution",
    "AppPaths",
    "get_app_paths",
    "initialize_paths",
    "ProcessResult",
    "run_process",
    "get_available_package_managers",
    "detect_primary_package_manager",
    "is_package_installed",
    "search_packages",
    "list_installed_packages",
    "get_package_info",
    "list_desktop_applications",
    "find_application_binary",
]
