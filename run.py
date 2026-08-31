"""
JARVIS PC — Main Entry Point.
Personal AI Voice Assistant for Linux with Cognitive Engine.

Two run modes:
  * UI mode (default when a display is available): a native GTK desktop app
    (main window + floating orb + tray). The cognitive engine runs on a
    background asyncio thread; GTK owns the main thread.
  * Headless mode (no display, or --no-ui): original text/voice + API server
    behaviour on the main asyncio loop.
"""

import asyncio
import signal
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.logger import get_logger, setup_logging

logger = get_logger("main")

_running = True
_stop_event = None  # set in UI mode to coordinate engine thread shutdown


def _signal_handler(sig, frame):
    global _running
    _running = False


def _should_run_ui() -> bool:
    """Decide whether to launch the native GTK UI."""
    if "--no-ui" in sys.argv:
        return False
    if "--headless" in sys.argv:
        return False
    display = __import__("os").environ.get("DISPLAY") or __import__("os").environ.get("WAYLAND_DISPLAY")
    if not display:
        return False
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401
        return True
    except Exception:
        logger.warning("GTK not importable; falling back to headless mode.")
        return False


async def _bootstrap_engine():
    """Build and start all cognitive subsystems. Returns an engine bundle."""
    from perception.event_bus import event_bus
    from perception.system_monitor import system_monitor
    from perception.application_monitor import app_monitor
    from perception.workflow_monitor import workflow_monitor
    from memory.memory_manager import memory_manager
    from tools.executor import tool_executor
    from tools.registry import tool_registry, ToolDef, ToolCategory, RiskLevel
    from proactive.engine import proactive_engine
    from cognitive.orchestrator import cognitive_orchestrator
    from core.observability import metrics

    # Wire up dependencies
    cognitive_orchestrator.inject_dependencies(
        llm_gateway=None,  # Set by voice pipeline
        tool_executor=tool_executor,
        event_bus=event_bus,
        memory_manager=memory_manager,
    )

    # Register builtin tools
    from llm.gateway import llm_gateway
    cognitive_orchestrator._llm_gateway = llm_gateway

    from tools.builtin import app_control, media_control, shell_exec, web_search
    _builtin_tools = [
        ToolDef(name="open_app", description="Open an application by name",
                category=ToolCategory.APPLICATION, risk_level=RiskLevel.LOW,
                handler=app_control.open_app,
                parameters={"app_name": {"type": "string", "required": True}}),
        ToolDef(name="close_app", description="Close an application",
                category=ToolCategory.APPLICATION, risk_level=RiskLevel.LOW,
                handler=app_control.close_app,
                parameters={"app_name": {"type": "string", "required": True}}),
        ToolDef(name="media_play", description="Play media or search music",
                category=ToolCategory.COMPUTER, risk_level=RiskLevel.LOW,
                handler=media_control.media_play,
                parameters={"query": {"type": "string", "required": False}}),
        ToolDef(name="media_pause", description="Pause media playback",
                category=ToolCategory.COMPUTER, risk_level=RiskLevel.LOW,
                handler=media_control.media_pause),
        ToolDef(name="set_volume", description="Set system volume level",
                category=ToolCategory.COMPUTER, risk_level=RiskLevel.LOW,
                handler=media_control.set_volume,
                parameters={"level": {"type": "string", "required": True}}),
        ToolDef(name="run_command", description="Execute a shell command",
                category=ToolCategory.SYSTEM, risk_level=RiskLevel.HIGH,
                handler=shell_exec.run_command, requires_confirmation=True,
                parameters={"command": {"type": "string", "required": True}}),
        ToolDef(name="web_search", description="Search the web",
                category=ToolCategory.NETWORK, risk_level=RiskLevel.LOW,
                handler=web_search.web_search,
                parameters={"query": {"type": "string", "required": True}}),
    ]
    for t in _builtin_tools:
        tool_registry.register(t)
    logger.info("Registered %d builtin tools", len(_builtin_tools))

    # Check hardware permissions (mic, speaker, camera)
    from voice.permissions import permission_manager
    permission_manager.print_status()

    # Register camera tools
    from tools.builtin import camera
    _camera_tools = [
        ToolDef(name="take_photo", description="Capture a photo from the webcam",
                category=ToolCategory.COMPUTER, risk_level=RiskLevel.SAFE,
                handler=camera.take_photo,
                parameters={"camera_index": {"type": "integer", "required": False}}),
        ToolDef(name="take_photo_sequence", description="Capture multiple photos with delay",
                category=ToolCategory.COMPUTER, risk_level=RiskLevel.SAFE,
                handler=camera.take_photo_sequence,
                parameters={"count": {"type": "integer", "required": False},
                            "delay": {"type": "number", "required": False},
                            "camera_index": {"type": "integer", "required": False}}),
        ToolDef(name="record_video", description="Record a short video clip from webcam",
                category=ToolCategory.COMPUTER, risk_level=RiskLevel.LOW,
                handler=camera.record_video,
                parameters={"duration": {"type": "number", "required": False},
                            "camera_index": {"type": "integer", "required": False}}),
        ToolDef(name="list_cameras", description="List available camera devices",
                category=ToolCategory.COMPUTER, risk_level=RiskLevel.SAFE,
                handler=camera.list_cameras),
    ]
    for t in _camera_tools:
        tool_registry.register(t)
    logger.info("Registered %d camera tools", len(_camera_tools))

    # Start all subsystems
    logger.info("Starting subsystems...")
    await event_bus.start()
    await system_monitor.start()
    await app_monitor.start()
    await workflow_monitor.start()
    await proactive_engine.start()
    await cognitive_orchestrator.start()

    # Start API server
    from api.server import jarvis_api
    jarvis_api.start(cognitive_orchestrator)

    # Voice pipeline (if hardware available)
    voice_available = False
    mic_status = permission_manager.mic
    speaker_status = permission_manager.speaker
    if mic_status and mic_status.available and speaker_status and speaker_status.available:
        try:
            from voice.pipeline import VoicePipeline
            pipeline = VoicePipeline(brain=cognitive_orchestrator)
            await pipeline.start()
            voice_available = True
            logger.info("Voice pipeline active (mic: %s, speaker: %s)", mic_status.name, speaker_status.name)
        except Exception as e:
            logger.warning("Voice pipeline unavailable: %s", e)
    else:
        reasons = []
        if not mic_status or not mic_status.available:
            reasons.append("mic unavailable")
        if not speaker_status or not speaker_status.available:
            reasons.append("speaker unavailable")
        logger.warning("Voice pipeline skipped: %s", ", ".join(reasons))

    bundle = types.SimpleNamespace(
        orchestrator=cognitive_orchestrator,
        event_bus=event_bus,
        world_state=__import__("cognitive.world_state", fromlist=["world_state"]).world_state,
        system_monitor=system_monitor,
        proactive_engine=proactive_engine,
        llm_gateway=llm_gateway,
        jarvis_api=jarvis_api,
        permission_manager=permission_manager,
        voice_available=voice_available,
    )
    logger.info("JARVIS is online. Systems nominal.")
    if voice_available:
        logger.info("Say 'Hey Jarvis' or use the JARVIS app.")
    else:
        logger.info("Text mode active (JARVIS app / API).")
    return bundle


async def _shutdown_engine(bundle):
    """Stop all subsystems gracefully."""
    logger.info("Shutting down JARVIS...")
    from proactive.engine import proactive_engine
    from cognitive.orchestrator import cognitive_orchestrator
    from perception.workflow_monitor import workflow_monitor
    from perception.application_monitor import app_monitor
    from perception.system_monitor import system_monitor
    from perception.event_bus import event_bus
    try:
        await proactive_engine.stop()
        await cognitive_orchestrator.stop()
        await workflow_monitor.stop()
        await app_monitor.stop()
        await system_monitor.stop()
        await event_bus.stop()
        bundle.jarvis_api.stop()
    except Exception as e:
        logger.error("Shutdown error: %s", e)
    logger.info("JARVIS offline. Goodbye.")


async def _ui_engine_main():
    """Engine loop for UI mode: runs on a background thread."""
    global _running
    bundle = await _bootstrap_engine()
    try:
        while _running:
            await asyncio.sleep(0.5)
    finally:
        await _shutdown_engine(bundle)


def _run_ui_mode():
    """Run the native GTK UI on the main thread; engine on a bg thread."""
    global _running, _stop_event
    import threading
    from gi.repository import GLib

    _stop_event = threading.Event()

    def _engine_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_ui_engine_main())
        except Exception as e:
            logger.error("Engine thread error: %s", e)
        finally:
            loop.close()

    et = threading.Thread(target=_engine_thread, daemon=True)
    et.start()

    # Give the engine a moment to bootstrap.
    et.join(0.01)

    # Launch GTK UI (blocks). The engine bundle is fetched from the now-running
    # orchestrator via a lightweight accessor.
    from ui.app import JarvisApp
    from cognitive.orchestrator import cognitive_orchestrator
    from perception.event_bus import event_bus
    from perception.system_monitor import system_monitor
    from proactive.engine import proactive_engine
    from llm.gateway import llm_gateway
    from cognitive.world_state import world_state

    class _Bundle:
        pass

    bundle = _Bundle()
    bundle.orchestrator = cognitive_orchestrator
    bundle.event_bus = event_bus
    bundle.world_state = world_state
    bundle.system_monitor = system_monitor
    bundle.proactive_engine = proactive_engine
    bundle.llm_gateway = llm_gateway

    # Patch quit so the GTK app also stops the engine thread.
    import ui.app as ui_app

    def _patched_quit(self):
        global _running
        _running = False
        try:
            self.bridge.stop()
        except Exception:
            pass
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        if self.floating_orb:
            self.floating_orb.orb.stop_animation()
        GLib.idle_add(self.quit)

    ui_app.JarvisApp._quit = _patched_quit

    app = JarvisApp(engine=bundle)
    app.run_app()


async def _legacy_main():
    """Original behaviour: text/voice + API server, no GTK UI."""
    global _running
    bundle = await _bootstrap_engine()
    logger.info("Press Ctrl+C to exit.")
    try:
        while _running:
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass
    finally:
        await _shutdown_engine(bundle)


def main():
    """Synchronous entry point."""
    setup_logging("INFO")
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    if _should_run_ui():
        logger.info("=" * 60)
        logger.info("  JARVIS PC — Native Desktop UI (Linux Mint)")
        logger.info("=" * 60)
        try:
            _run_ui_mode()
        except Exception as e:
            logger.error("UI mode failed, falling back to headless: %s", e)
            asyncio.run(_legacy_main())
    else:
        logger.info("=" * 60)
        logger.info("  JARVIS PC — Personal AI Voice Assistant")
        logger.info("  Cognitive Engine v1.0.0 (headless)")
        logger.info("=" * 60)
        try:
            asyncio.run(_legacy_main())
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
