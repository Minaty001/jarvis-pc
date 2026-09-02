"""CLI entrypoint for JARVIS."""
from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess  # nosec B404
import sys
import urllib.request
from typing import Sequence

from jarvis.app.application import Application
from jarvis.cli.doctor import run_doctor


def check_status() -> str:
    """Check real JARVIS service status via systemd and HTTP health check."""
    systemd_state = "unknown"
    try:
        systemctl_bin = shutil.which("systemctl") or "/bin/systemctl"
        result = subprocess.run(  # nosec B603 B607
            [systemctl_bin, "--user", "is-active", "jarvis.service"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        systemd_state = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    health_ok = False
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as resp:  # nosec B310
            if resp.status == 200:
                health_ok = True
    except Exception:  # nosec B110
        pass

    if systemd_state == "active" and health_ok:
        return "running"
    elif systemd_state == "active":
        return "starting"
    elif health_ok:
        return "running (unmanaged)"
    else:
        return "stopped"


def run_cli(args: Sequence[str] | None = None, app: Application | None = None) -> int:
    """Run JARVIS CLI with given arguments."""
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="JARVIS — Personal AI Voice Assistant for Linux",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommands")

    subparsers.add_parser("run", help="Run JARVIS assistant")
    subparsers.add_parser("doctor", help="Run system diagnostics check")
    subparsers.add_parser("status", help="Check JARVIS service status")
    subparsers.add_parser("version", help="Show JARVIS version")
    subparsers.add_parser("help", help="Show help message")

    parsed_args = parser.parse_args(args)

    if parsed_args.subcommand == "doctor":
        print(run_doctor())
    elif parsed_args.subcommand == "version":
        print("JARVIS CLI v1.0.0 (Linux)")
    elif parsed_args.subcommand == "status":
        state = check_status()
        print(f"JARVIS Status: {state}")
        return 0 if "running" in state else 1
    elif parsed_args.subcommand == "help":
        parser.print_help()
    elif parsed_args.subcommand == "run":
        print("Starting JARVIS v1.0.0...")
        application = app if app is not None else Application()
        asyncio.run(application.run_until_stopped())
    else:
        print("JARVIS CLI v1.0.0 (Linux)")

    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
