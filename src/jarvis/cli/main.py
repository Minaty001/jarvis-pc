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

    macro_parser = subparsers.add_parser("macro", help="Voice-Activated Workflow Macros & Action Pipelines")
    macro_sub = macro_parser.add_subparsers(dest="macro_action", help="Macro action")
    macro_sub.add_parser("list", help="List all configured workflow macros")
    
    m_run = macro_sub.add_parser("run", help="Execute a workflow macro by name")
    m_run.add_argument("name", help="Macro name (e.g. coding_mode, meeting_prep, lockdown, health_check)")
    m_run.add_argument("--var", action="append", help="Dynamic variable in key=value format (can be repeated)")

    m_ws = macro_sub.add_parser("create-workspace", help="Create a multi-app desktop workspace workflow")
    m_ws.add_argument("name", help="Workflow name (e.g. dev_mode)")
    m_ws.add_argument("--apps", required=True, help="Comma-separated app names (e.g. code,firefox,gnome-terminal)")
    m_ws.add_argument("--urls", help="Comma-separated URLs to open")
    m_ws.add_argument("--speech", help="Initial voice greeting announcement")

    m_record = macro_sub.add_parser("record", help="Start an interactive macro recording session")
    m_record.add_argument("name", help="Macro name to record")
    m_record.add_argument("--desc", default="", help="Description")

    macro_sub.add_parser("stop", help="Stop macro recording session and save definition")

    m_show = macro_sub.add_parser("show", help="Display details and steps of a workflow macro")
    m_show.add_argument("name", help="Macro name")

    m_toggle = macro_sub.add_parser("toggle", help="Enable or disable a workflow macro")
    m_toggle.add_argument("name", help="Macro name")
    m_toggle.add_argument("state", choices=["enable", "disable"], help="State to set")

    ctrl_parser = subparsers.add_parser("control", help="System & Hardware Control Hub (Volume, Brightness, Bluetooth, Wi-Fi, Power, Processes)")
    ctrl_sub = ctrl_parser.add_subparsers(dest="control_action", help="Control target")

    vol_p = ctrl_sub.add_parser("volume", help="Get or set system audio volume")
    vol_p.add_argument("level", nargs="?", type=int, default=None, help="Volume percentage (0-100)")
    vol_p.add_argument("--mute", action="store_true", help="Mute audio")
    vol_p.add_argument("--unmute", action="store_true", help="Unmute audio")

    bri_p = ctrl_sub.add_parser("brightness", help="Get or set display brightness")
    bri_p.add_argument("level", nargs="?", type=int, default=None, help="Brightness percentage (5-100)")

    bt_p = ctrl_sub.add_parser("bluetooth", help="Bluetooth adapter and device management")
    bt_p.add_argument("bt_action", choices=["list", "on", "off", "connect", "disconnect"], help="Action to perform")
    bt_p.add_argument("device", nargs="?", default=None, help="Device name or MAC address")

    wifi_p = ctrl_sub.add_parser("wifi", help="Network and Wi-Fi adapter control")
    wifi_p.add_argument("wifi_action", choices=["status", "list", "on", "off"], help="Action to perform")

    power_p = ctrl_sub.add_parser("power", help="System power and session management")
    power_p.add_argument("power_action", choices=["lock", "suspend", "reboot", "shutdown"], help="Power operation")
    power_p.add_argument("-y", "--yes", action="store_true", help="Confirm dangerous power operation")

    kill_p = ctrl_sub.add_parser("kill", help="Terminate process by name or PID")
    kill_p.add_argument("target", help="Process name or PID")
    kill_p.add_argument("-f", "--force", action="store_true", help="Force terminate with SIGKILL")

    close_p = ctrl_sub.add_parser("close", help="Close desktop window by title")
    close_p.add_argument("window", help="Window title")

    mem_parser = subparsers.add_parser("memory", help="Long-Term Semantic Memory & User Profile Knowledge Graph")
    mem_sub = mem_parser.add_subparsers(dest="memory_action", help="Memory action")

    mem_list = mem_sub.add_parser("list", help="List all stored semantic facts and memories")
    mem_list.add_argument("--category", default=None, help="Filter by category (e.g. preference, personal, work, tools)")
    mem_list.add_argument("--limit", type=int, default=50, help="Max items to list")

    mem_search = mem_sub.add_parser("search", help="Search memories using BM25 ranking")
    mem_search.add_argument("query", help="Search query")
    mem_search.add_argument("--category", default=None, help="Category filter")

    mem_rem = mem_sub.add_parser("remember", help="Save a user preference or fact into memory")
    mem_rem.add_argument("key", help="Fact key / identifier")
    mem_rem.add_argument("value", help="Fact value / description")
    mem_rem.add_argument("--category", default="preference", help="Category (default: preference)")

    mem_forg = mem_sub.add_parser("forget", help="Remove a fact from memory by key or ID")
    mem_forg.add_argument("target", help="Key or integer Record ID to delete")

    mem_sub.add_parser("profile", help="Show structured operator profile and preferences")
    mem_sub.add_parser("stats", help="Show memory storage metrics and database path")

    timer_parser = subparsers.add_parser("timer", help="Set and manage countdown timers")
    timer_parser.add_argument("duration", help="Timer duration (e.g. 10m, 45s, 1h 30m, 5m)")
    timer_parser.add_argument("label", nargs="?", default="Timer", help="Timer label / description")

    agenda_parser = subparsers.add_parser("agenda", help="Smart Agenda, Reminders, and Daily Schedule Hub")
    agenda_sub = agenda_parser.add_subparsers(dest="agenda_action", help="Agenda action")

    ag_list = agenda_sub.add_parser("list", help="List scheduled reminders and active timers")
    ag_list.add_argument("--all", action="store_true", help="Include completed and cancelled items")

    ag_add = agenda_sub.add_parser("add", help="Schedule a new reminder or calendar event")
    ag_add.add_argument("when", help="Time expression (e.g. 'tomorrow at 3pm', 'in 2 hours', 'today at 6pm')")
    ag_add.add_argument("title", help="Event / reminder title")
    ag_add.add_argument("--recurring", choices=["daily", "weekly"], default=None, help="Recurring schedule interval")

    ag_cancel = agenda_sub.add_parser("cancel", help="Cancel an agenda item or timer by ID")
    ag_cancel.add_argument("id", type=int, help="Agenda item ID")

    agenda_sub.add_parser("clear", help="Clear completed and cancelled agenda items")

    res_parser = subparsers.add_parser("research", help="Autonomous deep web research and factual synthesis")
    res_parser.add_argument("query", nargs="+", help="Research query or investigation topic")

    news_parser = subparsers.add_parser("news", help="Fetch real-time breaking news headlines")
    news_parser.add_argument("topic", nargs="?", default="tech", choices=["tech", "linux", "ai", "science", "security", "world"], help="News category / topic")
    news_parser.add_argument("--limit", type=int, default=6, help="Number of headlines to fetch")

    art_parser = subparsers.add_parser("article", help="Extract and read sanitized article content from URL")
    art_parser.add_argument("url", help="Web article URL")

    swarm_parser = subparsers.add_parser("swarm", help="Autonomous Multi-Agent Swarm & Background Worker Manager")
    swarm_sub = swarm_parser.add_subparsers(dest="swarm_action", help="Swarm action")

    sw_list = swarm_sub.add_parser("list", help="List active and recent swarm workers")
    sw_list.add_argument("--status", choices=["pending", "running", "completed", "failed", "cancelled"], default=None, help="Filter by status")
    sw_list.add_argument("--role", choices=["researcher", "coder", "system", "writer", "general"], default=None, help="Filter by worker role")
    sw_list.add_argument("--limit", type=int, default=20, help="Max tasks to show")

    sw_spawn = swarm_sub.add_parser("spawn", help="Spawn a new background sub-agent worker")
    sw_spawn.add_argument("role", choices=["researcher", "coder", "system", "writer", "general"], help="Worker role")
    sw_spawn.add_argument("instruction", help="Task instruction / prompt")
    sw_spawn.add_argument("--name", default="", help="Optional worker title")

    sw_show = swarm_sub.add_parser("show", help="Show details, logs, and output of a swarm task")
    sw_show.add_argument("id", help="Swarm task ID")

    sw_cancel = swarm_sub.add_parser("cancel", help="Cancel a running swarm worker")
    sw_cancel.add_argument("id", help="Swarm task ID")

    net_parser = subparsers.add_parser("network", help="Local Network Intelligence, IoT Device Discovery & Wake-on-LAN Hub")
    net_sub = net_parser.add_subparsers(dest="network_action", help="Network action")

    net_scan = net_sub.add_parser("scan", help="Scan local subnet for connected IoT devices, smart hubs, and workstations")
    net_scan.add_argument("--subnet", default="", help="Subnet base (e.g. '192.168.1')")
    net_scan.add_argument("--limit", type=int, default=30, help="Max hosts to scan")

    net_ping = net_sub.add_parser("ping", help="Ping a target host or IP for latency and jitter")
    net_ping.add_argument("host", help="Hostname or IP address")
    net_ping.add_argument("-c", "--count", type=int, default=3, help="Number of packets")

    net_wol = net_sub.add_parser("wol", help="Send Wake-on-LAN magic packet")
    net_wol.add_argument("mac", help="Target MAC address (e.g. 00:11:22:33:44:55)")
    net_wol.add_argument("--broadcast", default="255.255.255.255", help="Broadcast IP (default: 255.255.255.255)")

    net_sub.add_parser("bench", help="Run comprehensive network latency and speed benchmark")
    net_sub.add_parser("devices", help="List cached local network devices")

    pkg_parser = subparsers.add_parser("pkg", help="Linux Software Package Management & Inspection")
    pkg_sub = pkg_parser.add_subparsers(dest="pkg_action", help="Package action")

    pkg_check = pkg_sub.add_parser("check", help="Check if a software package is installed")
    pkg_check.add_argument("name", help="Package name")

    pkg_search = pkg_sub.add_parser("search", help="Search available software packages")
    pkg_search.add_argument("query", help="Search keyword")
    pkg_search.add_argument("--limit", type=int, default=15, help="Max results")

    pkg_list = pkg_sub.add_parser("list", help="List installed system packages")
    pkg_list.add_argument("--filter", default="", help="Filter query")
    pkg_list.add_argument("--limit", type=int, default=40, help="Max items")

    pkg_sub.add_parser("status", help="Show package manager status and backends")

    apps_parser = subparsers.add_parser("apps", help="Linux Desktop Application Discovery & Launching")
    apps_sub = apps_parser.add_subparsers(dest="apps_action", help="Apps action")
    apps_sub.add_parser("list", help="List all installed desktop applications")
    apps_open = apps_sub.add_parser("open", help="Launch a desktop application")
    apps_open.add_argument("name", help="Application name or ID")

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

    if parsed_args.subcommand == "macro":
        from jarvis.macros.engine import MacroEngine
        from jarvis.macros.store import MacroStore

        application = app if app is not None else Application()
        registry = getattr(getattr(application, "executor", None), "registry", None)
        if not registry and hasattr(application, "tools"):
            registry = getattr(application, "tools", None)
        engine = MacroEngine(tool_registry=registry)

        if parsed_args.macro_action == "list":
            macros = engine.store.list_macros()
            print("\nJARVIS Automated Workflow Macros:")
            print("=" * 70)
            for m in macros:
                status = "ENABLED" if m.enabled else "DISABLED"
                print(f"• {m.name:<22} [{status}] ({len(m.steps)} steps)")
                print(f"  Triggers:    {', '.join(m.triggers)}")
                print(f"  Description: {m.description}")
                print("-" * 70)
            print()
            return 0

        elif parsed_args.macro_action == "run":
            macro_name = parsed_args.name
            print(f"\n[JARVIS Macro] Executing workflow macro: '{macro_name}'...")

            # Parse runtime variables from --var key=value
            runtime_vars = {}
            if getattr(parsed_args, "var", None):
                for item in parsed_args.var:
                    if "=" in item:
                        k, v = item.split("=", 1)
                        runtime_vars[k.strip()] = v.strip()

            def on_step_progress(idx, step, out):
                print(f"  [{idx}/{len(macro_obj.steps)}] {step.type.value.upper()}: {step.description or step.target} -> {out[:80]}")

            macro_obj = engine.store.get_macro(macro_name)
            if not macro_obj:
                print(f"Error: Workflow macro '{macro_name}' not found.")
                return 1

            res = engine.execute_macro(macro_obj, variables=runtime_vars, on_step=on_step_progress)
            print("=" * 70)
            if res.success:
                print(f"Status: SUCCESS ({res.steps_completed}/{res.total_steps} steps executed)")
            else:
                print(f"Status: FAILED ({res.error})")
            print("=" * 70 + "\n")
            return 0 if res.success else 1

        elif parsed_args.macro_action == "create-workspace":
            from jarvis.tools.builtin.macro_tools import create_multi_app_workflow
            res = create_multi_app_workflow(
                name=parsed_args.name,
                apps=parsed_args.apps,
                urls=getattr(parsed_args, "urls", None),
                initial_speech=getattr(parsed_args, "speech", None),
            )
            print(f"\n[JARVIS Macro] {res}\n")
            return 0

        elif parsed_args.macro_action == "record":
            from jarvis.tools.builtin.macro_tools import start_recording_macro
            res = start_recording_macro(name=parsed_args.name, description=parsed_args.desc)
            print(f"\n[JARVIS Macro] {res}\n")
            return 0

        elif parsed_args.macro_action == "stop":
            from jarvis.tools.builtin.macro_tools import stop_recording_macro
            res = stop_recording_macro()
            print(f"\n[JARVIS Macro] {res}\n")
            return 0

        elif parsed_args.macro_action == "show":
            macro_obj = engine.store.get_macro(parsed_args.name)
            if not macro_obj:
                print(f"Macro '{parsed_args.name}' not found.")
                return 1
            print(f"\nWorkflow Macro: {macro_obj.name}")
            print("=" * 70)
            print(f"• Description: {macro_obj.description}")
            print(f"• Enabled:     {macro_obj.enabled}")
            print(f"• Triggers:    {', '.join(macro_obj.triggers)}")
            if macro_obj.variables:
                print(f"• Variables:   {macro_obj.variables}")
            print("\nPipeline Steps:")
            for idx, s in enumerate(macro_obj.steps, start=1):
                retry_str = f" [retries={s.retries}]" if s.retries else ""
                print(f"  {idx}. [{s.type.value.upper()}] target='{s.target}' args={s.args}{retry_str}")
            print("=" * 70 + "\n")
            return 0

        elif parsed_args.macro_action == "toggle":
            macro_obj = engine.store.get_macro(parsed_args.name)
            if not macro_obj:
                print(f"Macro '{parsed_args.name}' not found.")
                return 1
            enabled = parsed_args.state == "enable"
            macro_obj.enabled = enabled
            engine.store.save_macro(macro_obj)
            print(f"Macro '{macro_obj.name}' is now {'ENABLED' if enabled else 'DISABLED'}.")
            return 0

        else:
            print("Usage: jarvis macro {list|run|create-workspace|record|stop|show|toggle}")
            return 1

    if parsed_args.subcommand == "control":
        from jarvis.system.control import get_system_controller

        ctrl = get_system_controller()
        action = parsed_args.control_action

        if action == "volume":
            if parsed_args.mute:
                ctrl.audio.set_mute(True)
            elif parsed_args.unmute:
                ctrl.audio.set_mute(False)

            if parsed_args.level is not None:
                ctrl.audio.set_volume(parsed_args.level)

            info = ctrl.audio.get_volume()
            st = "MUTED" if info.get("muted") else "ACTIVE"
            print(f"System Volume: {info.get('percent')}% [{st}] (backend: {info.get('backend')})")
            return 0

        elif action == "brightness":
            if parsed_args.level is not None:
                ctrl.brightness.set_brightness(parsed_args.level)
            info = ctrl.brightness.get_brightness()
            print(f"Display Brightness: {info.get('percent')}% (backend: {info.get('backend')})")
            return 0

        elif action == "bluetooth":
            b_act = parsed_args.bt_action
            if b_act == "list":
                devs = ctrl.bluetooth.list_devices()
                if not devs:
                    print("No paired or available Bluetooth devices found.")
                else:
                    print(f"\nDiscovered {len(devs)} Bluetooth Device(s):")
                    print("-" * 65)
                    for d in devs:
                        print(f"• {d['mac']:<20} | {d['name']}")
                    print("-" * 65 + "\n")
            elif b_act == "on":
                ctrl.bluetooth.set_power(True)
                print("Bluetooth adapter powered ON.")
            elif b_act == "off":
                ctrl.bluetooth.set_power(False)
                print("Bluetooth adapter powered OFF.")
            elif b_act == "connect":
                if not parsed_args.device:
                    print("Error: Target device MAC or name required for connect.")
                    return 1
                ok = ctrl.bluetooth.connect_device(parsed_args.device)
                print(f"Connect to '{parsed_args.device}': {'SUCCESS' if ok else 'FAILED'}")
                return 0 if ok else 1
            elif b_act == "disconnect":
                if not parsed_args.device:
                    print("Error: Target device MAC or name required for disconnect.")
                    return 1
                ok = ctrl.bluetooth.disconnect_device(parsed_args.device)
                print(f"Disconnect from '{parsed_args.device}': {'SUCCESS' if ok else 'FAILED'}")
                return 0 if ok else 1
            return 0

        elif action == "wifi":
            w_act = parsed_args.wifi_action
            if w_act == "status":
                info = ctrl.network.get_status()
                print("\nNetwork Status:")
                print("=" * 60)
                print(f"• Connected:   {'YES' if info['connected'] else 'NO'}")
                print(f"• Active SSID: {info['ssid']}")
                print(f"• IP Address:  {info['ip']}")
                print(f"• Interface:   {info['interface']}")
                print("=" * 60 + "\n")
            elif w_act == "list":
                nets = ctrl.network.list_wifi()
                if not nets:
                    print("No Wi-Fi networks found.")
                else:
                    print(f"\nDiscovered {len(nets)} Wi-Fi Network(s):")
                    print("-" * 65)
                    for w in nets:
                        print(f"• {w['ssid']:<25} | Signal: {w['signal']}% | {w['security']}")
                    print("-" * 65 + "\n")
            elif w_act == "on":
                ctrl.network.set_wifi_power(True)
                print("Wi-Fi radio enabled.")
            elif w_act == "off":
                ctrl.network.set_wifi_power(False)
                print("Wi-Fi radio disabled.")
            return 0

        elif action == "power":
            p_act = parsed_args.power_action
            if p_act == "lock":
                ok = ctrl.power.lock_session()
                print("Session locked." if ok else "Failed to lock session.")
                return 0 if ok else 1
            if not parsed_args.yes:
                ans = input(f"Are you sure you want to perform system '{p_act}'? [y/N] ")
                if ans.strip().lower() not in ("y", "yes"):
                    print("Operation cancelled.")
                    return 0
            if p_act == "suspend":
                ctrl.power.suspend()
            elif p_act == "reboot":
                ctrl.power.reboot()
            elif p_act == "shutdown":
                ctrl.power.poweroff()
            return 0

        elif action == "kill":
            res = ctrl.process.kill_process(parsed_args.target, force=parsed_args.force)
            if res["success"]:
                print(f"Terminated {res['killed']} process(es) matching '{parsed_args.target}' (PIDs: {res['pids']}).")
                return 0
            print(f"No running processes found matching '{parsed_args.target}'.")
            return 1

        elif action == "close":
            ok = ctrl.process.close_window(parsed_args.window)
            print(f"Close window '{parsed_args.window}': {'SUCCESS' if ok else 'FAILED'}")
            return 0 if ok else 1

        else:
            print("Usage: jarvis control {volume|brightness|bluetooth|wifi|power|kill|close}")
            return 1

    if parsed_args.subcommand == "memory":
        from jarvis.brain.memory import MemoryStore
        from jarvis.system.paths import get_app_paths

        store = MemoryStore(get_app_paths().state / "memory.db")
        action = parsed_args.memory_action

        if action == "list":
            facts = store.list_facts(category=parsed_args.category, limit=parsed_args.limit)
            if not facts:
                print("No semantic facts or preferences recorded in memory yet.")
            else:
                print(f"\nJARVIS Stored Memories ({len(facts)} entries):")
                print("=" * 70)
                for f in facts:
                    print(f"[{f['id']:>3}] [{f['category'].upper():<10}] {f['key']:<20}: {f['value']}")
                print("=" * 70 + "\n")
            return 0

        elif action == "search":
            results = store.recall_facts(query=parsed_args.query, category=parsed_args.category, limit=10)
            if not results:
                print(f"No memories matched '{parsed_args.query}'.")
            else:
                print(f"\nMemory Search Results ({len(results)} matches for '{parsed_args.query}'):")
                print("=" * 70)
                for r in results:
                    print(f"• [{r['category'].upper():<10}] {r['key']:<20}: {r['value']} (confidence: {r['confidence']:.2f})")
                print("=" * 70 + "\n")
            return 0

        elif action == "remember":
            fid = store.store_fact(
                key=parsed_args.key,
                value=parsed_args.value,
                category=parsed_args.category,
                subject="user",
                predicate="preference",
                source="cli",
            )
            print(f"Memorized [{parsed_args.category}] '{parsed_args.key}': '{parsed_args.value}' (Record ID: {fid}).")
            return 0

        elif action == "forget":
            ok = store.delete_fact(parsed_args.target)
            if ok:
                print(f"Successfully deleted memory '{parsed_args.target}'.")
                return 0
            print(f"Memory '{parsed_args.target}' not found.")
            return 1

        elif action == "profile":
            profile = store.get_user_profile()
            if not profile:
                print("User profile is currently empty.")
            else:
                print("\nJARVIS Operator Profile & Stored Preferences:")
                print("=" * 65)
                for cat, items in profile.items():
                    print(f"\n[{cat.upper()}]")
                    for k, v in items.items():
                        print(f"• {k:<22}: {v}")
                print("=" * 65 + "\n")
            return 0

        elif action == "stats":
            summary = store.get_memory_summary()
            print("\nJARVIS Memory Subsystem Status:")
            print("=" * 60)
            print(f"• Semantic Facts & Knowledge: {summary['facts_count']}")
            print(f"• User Profile Attributes:    {summary['profile_keys_count']}")
            print(f"• Metacognitive Reflections:  {summary['reflections_count']}")
            print(f"• Episodic Chat Turns:        {summary['episodes_count']}")
            print(f"• Database Path:              {summary['db_path']}")
            print("=" * 60 + "\n")
            return 0

        else:
            print("Usage: jarvis memory {list|search|remember|forget|profile|stats}")
            return 1

    if parsed_args.subcommand == "timer":
        from jarvis.scheduler.agenda_engine import get_agenda_engine

        engine = get_agenda_engine()
        item_id, target_dt, sec = engine.set_timer(parsed_args.duration, label=parsed_args.label)
        time_str = target_dt.strftime("%I:%M:%S %p")
        print(f"\nCountdown Timer #{item_id} active for '{parsed_args.label}' ({parsed_args.duration}). Due at {time_str}.\n")
        return 0

    if parsed_args.subcommand == "agenda":
        import datetime
        from jarvis.scheduler.agenda_engine import get_agenda_engine

        engine = get_agenda_engine()
        action = parsed_args.agenda_action

        if action == "list":
            status_filter = None if getattr(parsed_args, "all", False) else "pending"
            items = engine.list_agenda(status=status_filter)
            if not items:
                print("\nNo pending reminders or active timers on your agenda.\n")
            else:
                print(f"\nJARVIS Agenda & Active Timers ({len(items)} items):")
                print("=" * 70)
                for it in items:
                    due_dt = datetime.datetime.fromtimestamp(it.due_timestamp)
                    due_str = due_dt.strftime("%Y-%m-%d %I:%M %p")
                    rec_str = f" [Recurring: {it.recurring}]" if it.recurring else ""
                    print(f"• #{it.id:<3} [{it.item_type.upper():<8}] {it.title:<25} | Due: {due_str} [{it.status.upper()}]{rec_str}")
                print("=" * 70 + "\n")
            return 0

        elif action == "add":
            item_id, target_dt, sec = engine.add_reminder(
                parsed_args.when,
                title=parsed_args.title,
                recurring=parsed_args.recurring,
            )
            time_str = target_dt.strftime("%A, %B %d at %I:%M %p")
            rec_str = f" [Recurring: {parsed_args.recurring}]" if parsed_args.recurring else ""
            print(f"\nScheduled Reminder #{item_id} for '{parsed_args.title}' on {time_str}{rec_str}.\n")
            return 0

        elif action == "cancel":
            ok = engine.cancel_item(parsed_args.id)
            if ok:
                print(f"\nAgenda item #{parsed_args.id} cancelled.\n")
                return 0
            print(f"\nAgenda item #{parsed_args.id} not found.\n")
            return 1

        elif action == "clear":
            count = engine.store.clear_completed()
            print(f"\nPurged {count} completed/cancelled agenda items.\n")
            return 0

        else:
            print("Usage: jarvis agenda {list|add|cancel|clear}")
            return 1

    if parsed_args.subcommand == "research":
        from jarvis.research.engine import get_research_engine

        query_str = " ".join(parsed_args.query) if isinstance(parsed_args.query, list) else str(parsed_args.query)
        print(f"\n[JARVIS Research Engine] Investigating: '{query_str}'...")
        application = app if app is not None else Application()
        client = getattr(application.agent, "client", None) if hasattr(application, "agent") else None
        engine = get_research_engine()
        res = asyncio.run(engine.research_topic(query_str, client=client))

        print("\n" + "=" * 70)
        print(res["summary"])
        print("=" * 70)
        if res.get("sources"):
            print(f"\nVerified Sources ({len(res['sources'])} references):")
            for s in res["sources"]:
                print(f"[{s['index']}] {s['title']}")
                print(f"    {s['url']}")
        print()
        return 0

    if parsed_args.subcommand == "news":
        from jarvis.research.news import fetch_news

        articles = asyncio.run(fetch_news(topic=parsed_args.topic, limit=parsed_args.limit))
        if not articles:
            print(f"No news headlines found for category '{parsed_args.topic}'.")
            return 1

        print(f"\nJARVIS Real-Time News Feed [{parsed_args.topic.upper()}] ({len(articles)} headlines):")
        print("=" * 70)
        for idx, a in enumerate(articles, start=1):
            print(f"[{idx}] {a['title']}")
            print(f"    Published: {a['published']}")
            print(f"    Summary:   {a['summary']}")
            print(f"    Source:    {a['url']}")
            print("-" * 70)
        print()
        return 0

    if parsed_args.subcommand == "article":
        from jarvis.research.extractor import extract_article

        res = asyncio.run(extract_article(parsed_args.url))
        if not res["success"]:
            print(f"\nError: {res['content']}\n")
            return 1

        print("\n" + "=" * 70)
        print(f"Title:  {res['title']}")
        print(f"Source: {res['url']} ({res['length']} chars)")
        print("=" * 70)
        print(res["content"])
        print("=" * 70 + "\n")
        return 0

    if parsed_args.subcommand == "swarm":
        from jarvis.swarm.engine import get_swarm_engine
        from jarvis.swarm.models import TaskStatus, WorkerRole

        engine = get_swarm_engine()
        action = parsed_args.swarm_action

        if action == "list":
            tasks = engine.list_tasks(status=parsed_args.status, role=parsed_args.role, limit=parsed_args.limit)
            if not tasks:
                print("\nNo swarm tasks found in database.\n")
                return 0

            print(f"\nJARVIS Autonomous Swarm Tasks ({len(tasks)} items):")
            print("=" * 80)
            print(f"{'ID':<16} | {'ROLE':<10} | {'STATUS':<11} | {'PROGRESS':<8} | {'NAME / INSTRUCTION'}")
            print("-" * 80)
            for t in tasks:
                r_str = t.role.value if isinstance(t.role, WorkerRole) else str(t.role)
                s_str = t.status.value if isinstance(t.status, TaskStatus) else str(t.status)
                title = t.name or (t.instruction[:40] + "..." if len(t.instruction) > 40 else t.instruction)
                print(f"{t.id:<16} | {r_str:<10} | {s_str:<11} | {t.progress_percent}%{'':<4} | {title}")
            print("=" * 80 + "\n")
            return 0

        elif action == "spawn":
            application = app if app is not None else Application()
            client = getattr(application.agent, "client", None) if hasattr(application, "agent") else None
            task = asyncio.run(
                engine.spawn_worker(
                    role=parsed_args.role,
                    instruction=parsed_args.instruction,
                    name=parsed_args.name,
                    client=client,
                )
            )
            print(f"\n[JARVIS Swarm] Sub-agent worker launched!")
            print(f"• Task ID:     {task.id}")
            print(f"• Name:        {task.name}")
            print(f"• Role:        {task.role.value}")
            print(f"• Status:      {task.status.value}")
            print(f"• Instruction: {task.instruction}\n")
            return 0

        elif action == "show":
            task = engine.get_task(parsed_args.id)
            if not task:
                print(f"\nSwarm task '{parsed_args.id}' not found.\n")
                return 1

            print("\n" + "=" * 75)
            print(f"Swarm Task: {task.name} ({task.id})")
            print(f"Role:       {task.role.value} | Status: {task.status.value} | Progress: {task.progress_percent}%")
            print(f"Created:    {task.created_at}")
            if task.started_at:
                print(f"Started:    {task.started_at}")
            if task.completed_at:
                print(f"Completed:  {task.completed_at}")
            print("-" * 75)
            print(f"Instruction:\n{task.instruction}")
            print("-" * 75)
            if task.result:
                print(f"Result Output:\n{task.result}")
                print("-" * 75)
            if task.error:
                print(f"Error:\n{task.error}")
                print("-" * 75)
            if task.logs:
                print(f"Execution Logs ({len(task.logs)} entries):")
                for l in task.logs:
                    print(f"[{l.get('timestamp', '')[:19]}] [{l.get('level', 'INFO')}] {l.get('message', '')}")
            print("=" * 75 + "\n")
            return 0

        elif action == "cancel":
            cancelled = asyncio.run(engine.cancel_task(parsed_args.id))
            if cancelled:
                print(f"\nSwarm task '{parsed_args.id}' successfully cancelled.\n")
                return 0
            print(f"\nCould not cancel task '{parsed_args.id}' (not running or not found).\n")
            return 1

        else:
            print("Usage: jarvis swarm {list|spawn|show|cancel}")
            return 1

    if parsed_args.subcommand == "network":
        from jarvis.network.hub import get_network_hub

        hub = get_network_hub()
        action = parsed_args.network_action

        if action == "scan":
            print("\n[JARVIS Network Hub] Scanning local subnet for connected IoT & network devices...")
            devices = asyncio.run(hub.scan_network(subnet_base=parsed_args.subnet, max_hosts=parsed_args.limit))
            if not devices:
                print("No network devices discovered on the subnet.\n")
                return 0

            print(f"\nDiscovered {len(devices)} Local Device(s):")
            print("=" * 80)
            print(f"{'IP ADDRESS':<16} | {'MAC ADDRESS':<18} | {'DEVICE TYPE / VENDOR':<26} | {'OPEN PORTS'}")
            print("-" * 80)
            for d in devices:
                ports_str = ",".join(str(p) for p in d.open_ports) if d.open_ports else "none"
                type_str = f"{d.device_type} ({d.vendor})" if d.vendor != "Unknown Vendor" else d.device_type
                if len(type_str) > 26:
                    type_str = type_str[:23] + "..."
                print(f"{d.ip:<16} | {d.mac:<18} | {type_str:<26} | {ports_str}")
            print("=" * 80 + "\n")
            return 0

        elif action == "ping":
            res = hub.ping(parsed_args.host, count=parsed_args.count)
            if not res["reachable"]:
                print(f"\nHost '{parsed_args.host}' is UNREACHABLE (100% packet loss).\n")
                return 1

            print(f"\nPing statistics for {res['host']}:")
            print("=" * 55)
            print("• Status:      ONLINE")
            print(f"• Avg Latency: {res['avg_ms']} ms (min: {res['min_ms']} ms, max: {res['max_ms']} ms)")
            print(f"• Jitter:      {res['jitter_ms']} ms")
            print(f"• Packet Loss: {res['packet_loss_percent']}%")
            print("=" * 55 + "\n")
            return 0

        elif action == "wol":
            ok = hub.wake_on_lan(parsed_args.mac, broadcast_ip=parsed_args.broadcast)
            if ok:
                print(f"\n[WoL] Magic packet successfully sent to {parsed_args.mac} (broadcast: {parsed_args.broadcast})\n")
                return 0
            print(f"\n[WoL] Failed to transmit packet to {parsed_args.mac}\n")
            return 1

        elif action == "bench":
            print("\n[JARVIS Network Hub] Running network diagnostics and latency benchmark...")
            bench = asyncio.run(hub.benchmark())
            status_str = "ONLINE" if bench["online"] else "OFFLINE"
            print("\n" + "=" * 60)
            print("JARVIS Network Diagnostic Report:")
            print("-" * 60)
            print(f"• Connectivity Status: {status_str}")
            print(f"• Overall Quality:     {bench['quality_score']}")
            print(f"• WAN Latency:         {bench['avg_latency_ms']} ms")
            print(f"• Jitter:              {bench['jitter_ms']} ms")
            print(f"• Packet Loss:         {bench['packet_loss_percent']}%")
            print(f"• DNS Resolution:      {bench['dns_lookup_ms']} ms ({bench['dns_status']})")
            if bench.get("http_rtt_ms") is not None:
                print(f"• HTTP Roundtrip:      {bench['http_rtt_ms']} ms")
            print("=" * 60 + "\n")
            return 0

        elif action == "devices":
            devices = hub.list_devices()
            if not devices:
                print("\nNo cached devices found in local registry. Run 'jarvis network scan' first.\n")
                return 0

            print(f"\nJARVIS Known Network Devices ({len(devices)} registered):")
            print("=" * 80)
            for d in devices:
                print(f"• {d.ip:<15} [{d.mac}] | {d.device_type} ({d.vendor}) | Hostname: {d.hostname}")
            print("=" * 80 + "\n")
            return 0

        else:
            print("Usage: jarvis network {scan|ping|wol|bench|devices}")
            return 1

    if parsed_args.subcommand == "pkg":
        from jarvis.system.packages import (
            detect_primary_package_manager,
            get_available_package_managers,
            get_package_info,
            is_package_installed,
            list_installed_packages,
            search_packages,
        )

        action = parsed_args.pkg_action
        if action == "check":
            installed = is_package_installed(parsed_args.name)
            info = get_package_info(parsed_args.name)
            print("\n" + "=" * 60)
            print(f"Package:     {parsed_args.name}")
            print(f"Status:      {'INSTALLED' if installed else 'NOT INSTALLED'}")
            if installed:
                print(f"Version:     {info.get('version', 'unknown')}")
                print(f"Description: {info.get('description', 'N/A')}")
            print("=" * 60 + "\n")
            return 0

        elif action == "search":
            results = search_packages(parsed_args.query, limit=parsed_args.limit)
            if not results:
                print(f"\nNo packages found matching query '{parsed_args.query}'.\n")
                return 0

            print(f"\nSearch results for '{parsed_args.query}' ({len(results)} found):")
            print("=" * 75)
            print(f"{'PACKAGE NAME':<28} | {'DESCRIPTION'}")
            print("-" * 75)
            for r in results:
                print(f"{r['name']:<28} | {r.get('description', '')[:42]}")
            print("=" * 75 + "\n")
            return 0

        elif action == "list":
            pkgs = list_installed_packages(filter_query=parsed_args.filter, limit=parsed_args.limit)
            if not pkgs:
                print("\nNo installed packages found matching filter.\n")
                return 0

            print(f"\nInstalled System Packages ({len(pkgs)} displayed):")
            print("=" * 60)
            for p in pkgs:
                print(f"• {p}")
            print("=" * 60 + "\n")
            return 0

        elif action == "status":
            mgrs = get_available_package_managers()
            primary = detect_primary_package_manager()
            print("\n" + "=" * 60)
            print("JARVIS Linux Package Management Subsystem:")
            print("-" * 60)
            print(f"• Primary Manager:    {primary.upper()}")
            print(f"• Available Backends: {', '.join(mgrs) if mgrs else 'None'}")
            print("=" * 60 + "\n")
            return 0

        else:
            print("Usage: jarvis pkg {check|search|list|status}")
            return 1

    if parsed_args.subcommand == "apps":
        from jarvis.system.packages import list_desktop_applications
        from jarvis.tools.builtin.applications import open_application

        action = parsed_args.apps_action
        if action == "list":
            apps = list_desktop_applications()
            if not apps:
                print("\nNo desktop applications discovered in standard application directories.\n")
                return 0

            print(f"\nJARVIS Discovered Desktop Applications ({len(apps)} total):")
            print("=" * 80)
            print(f"{'APPLICATION NAME':<30} | {'DESKTOP ID':<22} | {'COMMAND'}")
            print("-" * 80)
            for a in apps:
                print(f"{a['name']:<30} | {a['id']:<22} | {a['exec']}")
            print("=" * 80 + "\n")
            return 0

        elif action == "open":
            print(f"\n[JARVIS Apps] Launching desktop application: '{parsed_args.name}'...")
            try:
                res = asyncio.run(open_application(parsed_args.name))
                print(f"Application '{parsed_args.name}' launched successfully (PID output: {res.returncode}).\n")
                return 0
            except Exception as exc:
                print(f"Failed to launch application '{parsed_args.name}': {exc}\n")
                return 1

        else:
            print("Usage: jarvis apps {list|open}")
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
