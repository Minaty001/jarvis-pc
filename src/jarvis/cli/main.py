"""CLI entrypoint for JARVIS."""
from __future__ import annotations

import argparse
import asyncio
import os
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
            check=False,
        )
        systemd_state = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    health_ok = False
    try:
        from jarvis.config.settings import get_settings

        settings = get_settings()
        health_url = f"http://{settings.host}:{settings.port}/health"
        with urllib.request.urlopen(health_url, timeout=3) as resp:  # nosec B310
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

    run_parser = subparsers.add_parser("run", help="Run JARVIS assistant")
    run_parser.add_argument("--ui", action="store_true", help="Launch native GTK3 Desktop UI & Floating ORB")
    run_parser.add_argument("--no-ui", action="store_true", help="Run in CLI REPL mode without graphical interface")
    run_parser.add_argument("--headless", action="store_true", help="Run in headless daemon mode")

    subparsers.add_parser("ui", help="Launch native GTK3 Desktop UI & Floating ORB")
    subparsers.add_parser("goal", help="Plan, execute and verify a goal").add_argument(
        "goal", nargs="+", help="The goal to achieve"
    )
    subparsers.add_parser("reflections", help="Show learned lessons & procedural reflections")

    notify_parser = subparsers.add_parser("notify", help="Send a native desktop notification")
    notify_parser.add_argument("title", help="Notification title")
    notify_parser.add_argument("message", help="Notification message")
    notify_parser.add_argument(
        "--urgency", choices=["low", "normal", "critical"], default="normal", help="Urgency level"
    )

    subparsers.add_parser("proactive", help="Show active proactive background rules and health status")
    subparsers.add_parser("doctor", help="Run system diagnostics check")
    subparsers.add_parser("telegram", help="Run the Telegram bridge (phone access via the gateway)")
    subparsers.add_parser("status", help="Check JARVIS service status")
    subparsers.add_parser("version", help="Show JARVIS version")
    subparsers.add_parser("help", help="Show help message")

    voice_parser = subparsers.add_parser("voice", help="Voice commands (TTS, STT, wake word)")
    voice_sub = voice_parser.add_subparsers(dest="voice_action", help="Voice action")
    voice_sub.add_parser("speak", help="Speak text aloud").add_argument("text", help="Text to speak")
    voice_sub.add_parser("listen", help="Record once and transcribe (Groq whisper)")
    voice_sub.add_parser("wake", help="Wait until the wake word is spoken")
    voice_sub.add_parser("session", help="Full wake-word voice session with the JARVIS agent")

    parsed_args = parser.parse_args(args)

    if parsed_args.subcommand == "voice":
        return _run_voice(parsed_args, app)

    if parsed_args.subcommand == "telegram":
        from jarvis.remote.telegram import bridge_main

        bridge_main()
        return 0

    if parsed_args.subcommand == "notify":
        from jarvis.system.notifications import notify

        ok = notify(parsed_args.title, parsed_args.message, urgency=parsed_args.urgency)
        print(f"Notification sent: {'success' if ok else 'failed (logged)'}")
        return 0 if ok else 1

    if parsed_args.subcommand == "proactive":
        application = app if app is not None else Application()
        engine = getattr(application, "proactive", None)
        if engine and hasattr(engine, "list_rules"):
            rules = engine.list_rules()
            print("\nJARVIS Proactive Background Rules & Guardrails:")
            print("=" * 65)
            for r in rules:
                cooldown_str = f"{r['cooldown']:.0f}s"
                cooldown_status = "IN COOLDOWN" if r["in_cooldown"] else "READY"
                print(f"• Rule: {r['name']:<18} [{cooldown_status}]")
                print(f"  Description: {r['description']}")
                print(f"  Triggered:   {r['trigger_count']} times | Cooldown: {cooldown_str}")
                print("-" * 65)
        else:
            print("Proactive engine not active.")
        return 0

    if parsed_args.subcommand == "reflections":
        application = app if app is not None else Application()
        if hasattr(application.memory, "list_reflections"):
            reflections = application.memory.list_reflections(limit=15)
            if not reflections:
                print("No reflections or learned patterns recorded yet.")
            else:
                print("\nJARVIS Metacognitive Reflections & Learned Patterns:")
                print("=" * 60)
                for r in reflections:
                    status = "SUCCESS" if r["verified"] else "FAILED"
                    print(f"[{status}] Goal: {r['goal_query']}")
                    print(f"  Category: {r['category']}")
                    print(f"  Lesson:   {r['lesson']}")
                    if r.get("recipe"):
                        print(f"  Recipe:   {r['recipe']}")
                    print(f"  Stats:    {r['success_count']} successes / {r['failure_count']} failures")
                    print("-" * 60)
        else:
            print("Memory reflections subsystem not active.")
        return 0

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
    elif parsed_args.subcommand in ("ui", "run"):
        application = app if app is not None else Application()
        # Determine whether to launch UI or REPL
        want_ui = parsed_args.subcommand == "ui" or (
            getattr(parsed_args, "ui", False)
            or (
                not getattr(parsed_args, "no_ui", False)
                and not getattr(parsed_args, "headless", False)
                and "PYTEST_CURRENT_TEST" not in os.environ
                and bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
            )
        )
        if want_ui:
            try:
                from jarvis.ui.app import launch_ui

                return launch_ui(app_core=application)
            except Exception as exc:
                print(f"UI mode unavailable ({exc}), falling back to CLI REPL...")

        print("Starting JARVIS v1.0.0...")
        asyncio.run(_run_repl(application))
    elif parsed_args.subcommand == "goal":
        application = app if app is not None else Application()
        goal = " ".join(parsed_args.goal)
        print(f"Plan, execute & verify: {goal}")
        reply = asyncio.run(application.agent.run_goal(goal))
        print(f"\nResult: {reply}")
    else:
        print("JARVIS CLI v1.0.0 (Linux)")

    return 0


def _run_voice(parsed_args, app: Application | None) -> int:
    """Run voice commands: speak / listen / wake / full session."""
    from jarvis.voice import pipeline

    action = parsed_args.voice_action
    if action == "speak":
        from jarvis.config.settings import get_settings
        from jarvis.voice.tts import speak

        speak(parsed_args.text, voice=get_settings().voice)
        print(f"Spoke: {parsed_args.text}")
    elif action == "listen":
        print("Recording... (stop speaking to end)")
        text = pipeline.listen_once()
        print(f"Heard: {text!r}" if text else "Nothing heard.")
    elif action == "wake":
        print("Listening for wake word 'hey jarvis'... (Ctrl+C to stop)")
        pipeline.wait_for_wake()
        print("Wake word detected.")
    elif action == "session":
        application = app if app is not None else Application()
        agent = application.agent
        if not agent.confirmation_secret:
            agent.confirmation_secret = application.settings.confirmation_secret or "repl-local"

        def on_command(text: str) -> str:
            import asyncio

            return asyncio.run(agent.respond(text, session_id="voice"))

        pipeline.voice_loop(on_command)
    else:
        print("Usage: jarvis voice {speak|listen|wake|session}")
        return 1
    return 0


async def _run_repl(application: Application) -> None:
    """Interactive conversation loop with confirmation prompting."""
    import asyncio

    from jarvis.tools.confirmation import create_confirmation_token

    agent = application.agent
    secret = application.settings.confirmation_secret or "repl-local"

    async def confirm(tool_name: str, args: dict) -> str | None:
        if not secret:
            return None
        summary_parts = [f"{k}={v}" for k, v in args.items()]
        prompt = f"JARVIS requires approval to {tool_name} ({', '.join(summary_parts)}). Approve? [y/N] "
        answer = await asyncio.to_thread(input, prompt)
        if answer.strip().lower() not in ("y", "yes"):
            return None
        return create_confirmation_token(tool_name, args, agent_session, secret)

    agent.confirmation_resolver = confirm
    if not agent.confirmation_secret:
        agent.confirmation_secret = secret

    agent_session = "cli"

    print("JARVIS at your service. Type 'exit' or 'quit' to stop.")
    while True:
        try:
            line = await asyncio.to_thread(input, "> ")
        except (EOFError, KeyboardInterrupt):
            print("\nShutting down.")
            break
        line = line.strip()
        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            print("Goodbye.")
            break
        reply = await agent.respond(line, session_id="cli")
        print(reply)


if __name__ == "__main__":
    sys.exit(run_cli())
