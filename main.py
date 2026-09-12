#!/usr/bin/env python3
"""JARVIS Voice Assistant & Multi-Action Task Engine Entrypoint.

Starts listening automatically on launch and can run continuously in foreground,
background service mode, or execute direct CLI tasks.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from jarvis.audio_device import detect_and_configure_bluetooth_mic, get_active_microphone_name
from jarvis.engine import JarvisEngine
from jarvis.planner import TaskPlanner

PID_FILE = Path("/tmp/jarvis_wake_word.pid")
LOG_FILE = Path("/tmp/jarvis_wake_word.log")


def run_worker(threshold: float = 0.30, model: str = "hey_jarvis") -> None:
    """Internal runner for the listening process."""
    engine = JarvisEngine(
        threshold=threshold,
        model=model,
        auto_start=True,
    )

    def signal_handler(sig, frame):
        engine.stop()
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while engine.is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        engine.stop()


def run_foreground(threshold: float = 0.30, model: str = "hey_jarvis") -> None:
    """Run wake word detection & multi-action execution in foreground."""
    is_bt, mic_name = detect_and_configure_bluetooth_mic()

    print("=" * 65)
    print("🤖 JARVIS Voice Assistant & Task Engine Active")
    print(f"Wake Word   : {model}")
    print(f"Sensitivity : {threshold}")
    print(f"Microphone  : {mic_name} {'[BLUETOOTH CONNECTED]' if is_bt else '[SYSTEM DEFAULT]'}")
    print("Features    : Multi-action tasks, speech recognition, voice response")
    print("Say 'Hey Jarvis' to wake up. Press Ctrl+C to exit.")
    print("=" * 65, flush=True)

    run_worker(threshold=threshold, model=model)


def start_background(threshold: float = 0.30, model: str = "hey_jarvis") -> None:
    """Start JARVIS engine as a detached background service."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            print(f"JARVIS service is already running (PID: {pid}).")
            return
        except OSError:
            PID_FILE.unlink(missing_ok=True)

    log_fd = open(LOG_FILE, "a")
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--threshold",
        str(threshold),
        "--model",
        model,
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=log_fd,
        stderr=log_fd,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    PID_FILE.write_text(str(proc.pid))
    print(f"Started JARVIS background service (PID: {proc.pid}).")
    print(f"Logs: {LOG_FILE}")


def stop_background() -> None:
    """Stop running background service."""
    if not PID_FILE.exists():
        print("No background JARVIS service found.")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.3)
        PID_FILE.unlink(missing_ok=True)
        print(f"Stopped JARVIS background service (PID: {pid}).")
    except OSError as err:
        print(f"Process PID {pid} not reachable: {err}")
        PID_FILE.unlink(missing_ok=True)


def check_status() -> None:
    """Check status of background service."""
    if not PID_FILE.exists():
        print("JARVIS status: INACTIVE")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        print(f"JARVIS status: ACTIVE (running in background, PID {pid})")
        print(f"Log file: {LOG_FILE}")
    except OSError:
        print("JARVIS status: INACTIVE (stale PID removed)")
        PID_FILE.unlink(missing_ok=True)


def run_command_direct(cmd_text: str) -> None:
    """Execute a text-based multi-action command directly."""
    print(f"\n⚡ Executing command: \"{cmd_text}\"")
    planner = TaskPlanner()
    report = planner.process(cmd_text)

    print("\n" + "-" * 50)
    print(f"📋 Tasks Executed: {len(report.results)}")
    for idx, res in enumerate(report.results, 1):
        icon = "✅" if res.success else "❌"
        print(f"  {idx}. {icon} {res.message}")
    print("-" * 50)
    print(f"🔊 JARVIS: {report.summary_message}\n")


def main() -> None:
    """Parse CLI arguments and run JARVIS service."""
    parser = argparse.ArgumentParser(description="JARVIS Voice Assistant & Task Engine")
    parser.add_argument("--background", "--daemon", "-d", action="store_true", help="Run service in background")
    parser.add_argument("--stop", action="store_true", help="Stop background service")
    parser.add_argument("--status", action="store_true", help="Check background service status")
    parser.add_argument("--cmd", "-c", type=str, help="Execute a multi-action command directly via text")
    parser.add_argument("--model", type=str, default="hey_jarvis", help="Wake word model name (default: hey_jarvis)")
    parser.add_argument("--threshold", type=float, default=0.30, help="Detection confidence threshold (default: 0.30)")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.cmd:
        run_command_direct(args.cmd)
    elif args.worker:
        run_worker(threshold=args.threshold, model=args.model)
    elif args.stop:
        stop_background()
    elif args.status:
        check_status()
    elif args.background:
        start_background(threshold=args.threshold, model=args.model)
    else:
        run_foreground(threshold=args.threshold, model=args.model)


if __name__ == "__main__":
    main()
