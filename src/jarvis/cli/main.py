"""CLI entrypoint for JARVIS."""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess  # nosec B404
import sys
import time
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

    voice_parser = subparsers.add_parser("voice", help="Voice commands (TTS, STT, wake word, profiles)")
    voice_sub = voice_parser.add_subparsers(dest="voice_action", help="Voice action")
    voice_sub.add_parser("speak", help="Speak text aloud").add_argument("text", help="Text to speak")
    voice_sub.add_parser("listen", help="Record once and transcribe (Groq whisper)")
    voice_sub.add_parser("wake", help="Wait until the wake word is spoken")
    voice_sub.add_parser("session", help="Full wake-word voice session with the JARVIS agent")
    voice_sub.add_parser("profiles", help="List all available neural voice personality profiles")
    set_prof_p = voice_sub.add_parser("set-profile", help="Activate a neural voice personality profile")
    set_prof_p.add_argument("name", help="Profile name (e.g. british_butler, classic_jarvis, tactical_ai, indian_english, hindi_assistant, etc.)")
    auto_wake_p = voice_sub.add_parser("auto-wake", help="Run continuous low-power background wake-word daemon")
    auto_wake_p.add_argument("--phrases", default=None, help="Comma-separated trigger phrases (default: 'hey jarvis,jarvis')")
    auto_wake_p.add_argument("--no-ack", action="store_true", help="Disable acoustic 'Yes, sir?' acknowledgment")
    auto_wake_p.add_argument("--timeout", type=float, default=6.0, help="Conversational turn follow-up timeout in seconds")
    voice_sub.add_parser("auto-wake-status", help="Inspect ambient wake-word service status and configuration")

    cam_parser = subparsers.add_parser("camera", help="Camera discovery and snapshot capture")
    cam_sub = cam_parser.add_subparsers(dest="camera_action", help="Camera action")
    cam_sub.add_parser("list", help="List detected video devices")
    snap_p = cam_sub.add_parser("snap", help="Take a photo from the camera")
    snap_p.add_argument("--device", default="/dev/video0", help="Camera device path (default: /dev/video0)")
    snap_p.add_argument("--output", default=None, help="Output file path (default: ~/Pictures/...)")

    llm_parser = subparsers.add_parser("llm", help="Inspect LLM providers (Cloud & Local Ollama)")
    llm_sub = llm_parser.add_subparsers(dest="llm_action", help="LLM action")
    llm_sub.add_parser("status", help="Check Cloud and Local Ollama endpoint health")

    screen_parser = subparsers.add_parser("screen", help="Screen capture and window awareness")
    screen_sub = screen_parser.add_subparsers(dest="screen_action", help="Screen action")
    screen_snap = screen_sub.add_parser("snap", help="Take a full desktop screenshot")
    screen_snap.add_argument("--output", default=None, help="Output image path (default: ~/Pictures/...)")
    screen_sub.add_parser("active", help="Get currently focused active window")
    screen_sub.add_parser("list", help="List all open desktop windows")
    
    scr_click = screen_sub.add_parser("click", help="Click at desktop (X, Y) coordinates")
    scr_click.add_argument("x", type=int, help="X pixel coordinate")
    scr_click.add_argument("y", type=int, help="Y pixel coordinate")
    scr_click.add_argument("--button", default="left", choices=["left", "right", "middle"], help="Mouse button")
    scr_click.add_argument("--clicks", type=int, default=1, help="Number of clicks")

    scr_type = screen_sub.add_parser("type", help="Type text into focused window")
    scr_type.add_argument("text", help="Text to type")

    scr_key = screen_sub.add_parser("key", help="Press a key or key combination")
    scr_key.add_argument("key", help="Key name (Return, Escape, Tab, ctrl+c, alt+Tab, etc.)")

    scr_focus = screen_sub.add_parser("focus", help="Focus window by title or hex ID")
    scr_focus.add_argument("window", help="Window title or ID")

    scr_locate = screen_sub.add_parser("locate", help="Visually locate element on screen and click it")
    scr_locate.add_argument("description", help="Description of element (e.g. 'Submit button', 'Settings icon')")

    vision_parser = subparsers.add_parser("vision", help="Multimodal vision analysis")
    vision_sub = vision_parser.add_subparsers(dest="vision_action", help="Vision action")
    vis_an = vision_sub.add_parser("analyze", help="Analyze an image file using computer vision")
    vis_an.add_argument("image_path", help="Path to image file")
    vis_an.add_argument("--prompt", default="Describe what you see in this image in detail.", help="Question or prompt")

    code_parser = subparsers.add_parser("code", help="Multi-agent coding copilot for autonomous refactoring and test generation")
    code_parser.add_argument("task", help="Coding task or refactor instruction")
    code_parser.add_argument("--path", default=".", help="Workspace path (default: current directory)")
    code_parser.add_argument("--no-commit", action="store_true", help="Do not automatically commit after tests pass")

    weather_parser = subparsers.add_parser("weather", help="Query current live weather and forecasts")
    weather_parser.add_argument("location", nargs="?", default="auto", help="Location or city (default: auto-detected)")

    briefing_parser = subparsers.add_parser("briefing", help="Generate or speak comprehensive situational daily briefing")
    briefing_parser.add_argument("--location", default=None, help="Location or city override")
    briefing_parser.add_argument("--speak", action="store_true", help="Read briefing aloud via neural TTS")

    knowledge_parser = subparsers.add_parser("knowledge", help="Personal Knowledge Base & Local File Semantic Search (RAG)")
    knowledge_sub = knowledge_parser.add_subparsers(dest="knowledge_action", help="Knowledge action")
    
    k_search = knowledge_sub.add_parser("search", help="Search indexed local files with BM25")
    k_search.add_argument("query", help="Search query")
    k_search.add_argument("--limit", type=int, default=5, help="Max results (default: 5)")
    k_search.add_argument("--pattern", default=None, help="File path pattern filter")

    k_index = knowledge_sub.add_parser("index", help="Index a directory into the local knowledge base")
    k_index.add_argument("path", nargs="?", default=".", help="Directory path to index (default: current directory)")
    k_index.add_argument("--no-recursive", action="store_true", help="Do not index subdirectories recursively")
    k_index.add_argument("--force", action="store_true", help="Force re-indexing of all files")

    k_ask = knowledge_sub.add_parser("ask", help="Ask a question answered via local documents with citations")
    k_ask.add_argument("question", help="Question to ask")

    knowledge_sub.add_parser("status", help="Show knowledge base metrics and database path")
    knowledge_sub.add_parser("list", help="List all currently indexed files")

    parsed_args = parser.parse_args(args)

    if parsed_args.subcommand == "voice":
        return _run_voice(parsed_args, app)

    if parsed_args.subcommand == "camera":
        from jarvis.tools.builtin.camera import list_cameras, take_photo

        if parsed_args.camera_action == "list":
            cameras = list_cameras()
            if not cameras:
                print("No camera devices detected on this system.")
            else:
                print(f"\nDiscovered {len(cameras)} Camera Device(s):")
                print("-" * 65)
                for cam in cameras:
                    acc_str = "ACCESSIBLE" if cam["accessible"] else "PERMISSION DENIED"
                    print(f"• {cam['device']:<14} | {cam['name']} [{acc_str}]")
                print("-" * 65)
            return 0
        elif parsed_args.camera_action == "snap":
            try:
                res = asyncio.run(take_photo(output_path=parsed_args.output, device_path=parsed_args.device))
                print(res)
                return 0
            except Exception as exc:
                print(f"Failed to capture photo: {exc}")
                return 1
        else:
            print("Usage: jarvis camera {list|snap}")
            return 1

    if parsed_args.subcommand == "llm":
        from jarvis.brain.client import LLMClient

        application = app if app is not None else Application()
        client = getattr(application.agent, "client", None)
        if not client or not isinstance(client, LLMClient):
            client = LLMClient.from_settings(application.settings)

        if parsed_args.llm_action == "status":
            health = asyncio.run(client.check_health())
            print("\nJARVIS Multi-Tier LLM Architecture Status:")
            print("=" * 65)
            cloud = health["cloud"]
            cloud_status = "CONFIGURED (API Key Present)" if cloud["available"] else "NOT CONFIGURED (No Key)"
            print(f"• Primary Cloud LLM:   {cloud_status}")
            print(f"  Endpoint:            {cloud['base_url']}")
            print(f"  Model:               {cloud['model']}")
            print("-" * 65)
            local = health["local"]
            local_reach = "ONLINE & REACHABLE" if local["reachable"] else "OFFLINE / UNREACHABLE"
            print(f"• Local Offline LLM:   {local_reach}")
            print(f"  Endpoint:            {local['base_url']}")
            print(f"  Model:               {local['model']}")
            print(f"  Failover Enabled:    {local['enabled']}")
            print("-" * 65)
            print(f"★ Active Cognitive Mode: {health['active_mode'].upper()}")
            print("=" * 65)
            return 0
        else:
            print("Usage: jarvis llm status")
            return 1

    if parsed_args.subcommand == "screen":
        from jarvis.tools.builtin.screen import take_screenshot, get_active_window, list_open_windows

        if parsed_args.screen_action == "snap":
            try:
                res = asyncio.run(take_screenshot(output_path=parsed_args.output))
                print(res)
                return 0
            except Exception as exc:
                print(f"Failed to capture screenshot: {exc}")
                return 1
        elif parsed_args.screen_action == "active":
            info = asyncio.run(get_active_window())
            if "error" in info:
                print(f"Active window query: {info['error']}")
            else:
                print("\nCurrently Active Window:")
                print("-" * 50)
                print(f"• Title:       {info.get('title')}")
                print(f"• Application: {info.get('app_class')}")
                print(f"• Window ID:   {info.get('window_id')}")
                print("-" * 50)
            return 0
        elif parsed_args.screen_action == "list":
            windows = asyncio.run(list_open_windows())
            if not windows:
                print("No open application windows detected.")
            else:
                print(f"\nOpen Windows ({len(windows)}):")
                print("-" * 65)
                for w in windows:
                    print(f"• {w['window_id']:<12} | {w['app_class']:<25} | {w['title']}")
                print("-" * 65)
            return 0
        elif parsed_args.screen_action == "click":
            from jarvis.tools.builtin.desktop_automation import click_mouse
            msg = asyncio.run(click_mouse(parsed_args.x, parsed_args.y, button=parsed_args.button, clicks=parsed_args.clicks))
            print(msg)
            return 0
        elif parsed_args.screen_action == "type":
            from jarvis.tools.builtin.desktop_automation import type_text
            msg = asyncio.run(type_text(parsed_args.text))
            print(msg)
            return 0
        elif parsed_args.screen_action == "key":
            from jarvis.tools.builtin.desktop_automation import press_key
            msg = asyncio.run(press_key(parsed_args.key))
            print(msg)
            return 0
        elif parsed_args.screen_action == "focus":
            from jarvis.tools.builtin.desktop_automation import focus_window
            msg = asyncio.run(focus_window(parsed_args.window))
            print(msg)
            return 0
        elif parsed_args.screen_action == "locate":
            from jarvis.tools.builtin.desktop_automation import locate_and_click
            application = app if app is not None else Application()
            client = getattr(application.agent, "client", None) if hasattr(application, "agent") else None
            msg = asyncio.run(locate_and_click(parsed_args.description, client=client))
            print(msg)
            return 0
        else:
            print("Usage: jarvis screen {snap|active|list|click|type|key|focus|locate}")
            return 1

    if parsed_args.subcommand == "vision":
        from jarvis.tools.builtin.vision import analyze_image

        if parsed_args.vision_action == "analyze":
            application = app if app is not None else Application()
            client = getattr(application.agent, "client", None)
            try:
                reply = asyncio.run(
                    analyze_image(parsed_args.image_path, prompt=parsed_args.prompt, client=client)
                )
                print(f"\nJARVIS Visual Analysis:")
                print("-" * 65)
                print(reply)
                print("-" * 65)
                return 0
            except Exception as exc:
                print(f"Visual analysis failed: {exc}")
                return 1
        else:
            print("Usage: jarvis vision analyze <image_path> [--prompt ...]")
            return 1

    if parsed_args.subcommand == "code":
        from jarvis.brain.coder.orchestrator import CodingCopilot

        application = app if app is not None else Application()
        client = getattr(application.agent, "client", None) if hasattr(application, "agent") else None
        copilot = CodingCopilot(llm_client=client)

        print(f"\n[JARVIS Copilot] Starting multi-agent coding pipeline for task: '{parsed_args.task}'")
        res = asyncio.run(
            copilot.execute_task(
                parsed_args.task,
                workspace_path=parsed_args.path,
                auto_commit=not parsed_args.no_commit,
            )
        )
        print("\n" + "=" * 65)
        print(f"Status:         {'SUCCESS' if res.success else 'FAILED'}")
        print(f"Branch:         {res.branch}")
        print(f"Strategy:       {res.plan}")
        print(f"Modified Files: {', '.join(res.files_modified) if res.files_modified else '(none)'}")
        if res.commit_info:
            print(f"Commit:         {res.commit_info}")
        if res.error:
            print(f"Error:          {res.error}")
        print("=" * 65 + "\n")
        return 0 if res.success else 1

    if parsed_args.subcommand == "weather":
        from jarvis.tools.builtin.weather import get_weather

        weather_report = asyncio.run(get_weather(parsed_args.location))
        print(f"\n{weather_report}\n")
        return 0

    if parsed_args.subcommand == "briefing":
        from jarvis.proactive.briefing import generate_briefing, speak_briefing

        application = app if app is not None else Application()
        client = getattr(application.agent, "client", None) if hasattr(application, "agent") else None

        if parsed_args.speak:
            print("\n[JARVIS] Presenting spoken daily briefing...")
            briefing_text = asyncio.run(speak_briefing(location=parsed_args.location, client=client))
        else:
            briefing_text = asyncio.run(generate_briefing(location=parsed_args.location, client=client))

        print("\n" + "=" * 65)
        print("JARVIS SITUATIONAL DAILY BRIEFING")
        print("=" * 65)
        print(briefing_text)
        print("=" * 65 + "\n")
        return 0

    if parsed_args.subcommand == "knowledge":
        from jarvis.knowledge.indexer import KnowledgeIndexer
        from jarvis.knowledge.rag import KnowledgeAssistant
        from jarvis.knowledge.store import KnowledgeStore

        store = KnowledgeStore()

        if parsed_args.knowledge_action == "search":
            results = store.search(
                query=parsed_args.query,
                limit=parsed_args.limit,
                file_pattern=parsed_args.pattern,
            )
            if not results:
                print(f"No results found for query '{parsed_args.query}'.")
            else:
                print(f"\nKnowledge Search Results ({len(results)} matches for '{parsed_args.query}'):")
                print("=" * 70)
                for i, r in enumerate(results, start=1):
                    print(f"[{i}] {r['path']} (Lines {r['start_line']}-{r['end_line']}) [Rank: {r['score']}]")
                    snippet = "\n    ".join(r["content"].strip().splitlines()[:5])
                    print(f"    {snippet}")
                    print("-" * 70)
                print()
            return 0

        elif parsed_args.knowledge_action == "index":
            indexer = KnowledgeIndexer(store=store)
            rec = not parsed_args.no_recursive
            print(f"Scanning and indexing '{parsed_args.path}' (recursive={rec})...")
            res = indexer.index_directory(parsed_args.path, recursive=rec, force=parsed_args.force)
            print(f"Index complete: {res['indexed']} indexed, {res['skipped']} skipped, {res['errors']} errors.")
            return 0

        elif parsed_args.knowledge_action == "ask":
            application = app if app is not None else Application()
            client = getattr(application.agent, "client", None) if hasattr(application, "agent") else None
            assistant = KnowledgeAssistant(store=store, llm_client=client)
            print(f"\n[JARVIS Knowledge RAG] Synthesizing answer for: '{parsed_args.question}'...")
            reply = assistant.ask(parsed_args.question)
            print("\n" + "=" * 70)
            print(reply)
            print("=" * 70 + "\n")
            return 0

        elif parsed_args.knowledge_action == "status":
            stats = store.get_stats()
            mb = stats["total_bytes"] / (1024 * 1024)
            print("\nJARVIS Knowledge Base Status:")
            print("=" * 60)
            print(f"• Total Indexed Files:  {stats['total_files']}")
            print(f"• Total Text Chunks:    {stats['total_chunks']}")
            print(f"• Total Indexed Size:   {mb:.2f} MB")
            print(f"• Database Path:        {stats['db_path']}")
            print("=" * 60 + "\n")
            return 0

        elif parsed_args.knowledge_action == "list":
            files = store.list_files(limit=50)
            if not files:
                print("No files indexed in knowledge base yet. Run 'jarvis knowledge index <path>' to start.")
            else:
                print(f"\nIndexed Files ({len(files)}):")
                print("=" * 70)
                for f in files:
                    kb = f["size"] / 1024
                    print(f"• {f['path']} ({f['chunks_count']} chunks, {kb:.1f} KB)")
                print("=" * 70 + "\n")
            return 0
        else:
            print("Usage: jarvis knowledge {search|index|ask|status|list}")
            return 1

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
    elif action == "profiles":
        from jarvis.voice.profiles import VoiceProfileManager

        mgr = VoiceProfileManager()
        active = mgr.get_active_profile()
        print("\nJARVIS Neural Voice Personality Profiles:")
        print("=" * 70)
        for p in mgr.list_profiles():
            marker = "★ [ACTIVE]" if p["key"] == active.key else "          "
            print(f"{marker} {p['key']:<16} | {p['name']:<20} | {p['language']} ({p['gender']})")
            print(f"             Voice: {p['voice']} | Rate: {p['rate']} | Pitch: {p['pitch']}")
            print(f"             Desc:  {p['description']}")
            print("-" * 70)
        print()
    elif action == "set-profile":
        from jarvis.voice.profiles import VoiceProfileManager

        mgr = VoiceProfileManager()
        try:
            prof = mgr.set_profile(parsed_args.name)
            print(f"\nSuccessfully activated voice profile '{prof.key}' ({prof.name}).")
            print(f"Voice: {prof.voice} | Rate: {prof.rate} | Pitch: {prof.pitch}\n")
        except Exception as exc:
            print(f"Error setting voice profile: {exc}")
            return 1
    elif action == "auto-wake":
        from jarvis.config.settings import get_settings
        from jarvis.voice.auto_wake import AutoWakeService

        application = app if app is not None else Application()
        agent = application.agent
        if not agent.confirmation_secret:
            agent.confirmation_secret = application.settings.confirmation_secret or "repl-local"

        def on_command(text: str) -> str:
            import asyncio
            return asyncio.run(agent.respond(text, session_id="voice-auto-wake"))

        phrases = [p.strip() for p in parsed_args.phrases.split(",")] if parsed_args.phrases else None
        ack = "" if parsed_args.no_ack else None

        print("\nStarting continuous low-power AutoWakeService daemon...")
        print("Press Ctrl+C to terminate.")
        print("-" * 65)

        service = AutoWakeService(
            on_command=on_command,
            phrases=phrases,
            ack_phrase=ack,
            followup_timeout=parsed_args.timeout,
            on_status=lambda s: print(f"[{time.strftime('%H:%M:%S')}] {s}"),
            on_chat=lambda r, t: print(f"[{r.upper()}] {t}"),
        )
        service.start()
        try:
            while service.is_running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nShutting down AutoWakeService...")
        finally:
            service.stop()
            print("AutoWakeService terminated.\n")
    elif action == "auto-wake-status":
        from jarvis.config.settings import get_settings
        settings = get_settings()
        print("\nJARVIS Ambient Wake-Word Configuration & Status:")
        print("=" * 65)
        print(f"• Auto Wake Enabled:     {'YES' if settings.auto_wake_word else 'NO'}")
        print(f"• Trigger Phrases:       {settings.wake_phrases}")
        print(f"• Acknowledgment Prompt: {settings.wake_ack_phrase}")
        print(f"• Follow-up Timeout:     {settings.wake_followup_timeout}s")
        print(f"• Silence Energy Gate:   {settings.wake_vad_threshold} (Low-Power VAD)")
        print(f"• Full-Duplex Barge-in:  {'ENABLED' if settings.voice_barge_in else 'DISABLED'}")
        print("=" * 65 + "\n")
    else:
        print("Usage: jarvis voice {speak|listen|wake|session|profiles|set-profile|auto-wake|auto-wake-status}")
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
