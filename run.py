"""
JARVIS PC — Main Entry Point.
Personal AI Voice Assistant for Linux with Cognitive Engine.
"""

import asyncio
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.logger import get_logger, setup_logging

logger = get_logger("main")

_running = True


def _signal_handler(sig, frame):
    global _running
    _running = False


async def main():
    """Main entry point for JARVIS with full cognitive engine."""
    global _running

    setup_logging("INFO")
    logger.info("=" * 60)
    logger.info("  JARVIS PC — Personal AI Voice Assistant")
    logger.info("  Cognitive Engine v1.0.0")
    logger.info("=" * 60)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Initialize core components
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
                parameters={
                    "count": {"type": "integer", "required": False},
                    "delay": {"type": "number", "required": False},
                    "camera_index": {"type": "integer", "required": False},
                }),
        ToolDef(name="record_video", description="Record a short video clip from webcam",
                category=ToolCategory.COMPUTER, risk_level=RiskLevel.LOW,
                handler=camera.record_video,
                parameters={
                    "duration": {"type": "number", "required": False},
                    "camera_index": {"type": "integer", "required": False},
                }),
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

    # Start voice pipeline (if hardware available)
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
            logger.info("Running in text-only mode (API on http://127.0.0.1:3000)")
    else:
        reasons = []
        if not mic_status or not mic_status.available:
            reasons.append("mic unavailable")
        if not speaker_status or not speaker_status.available:
            reasons.append("speaker unavailable")
        logger.warning("Voice pipeline skipped: %s", ", ".join(reasons))
        logger.info("Running in text-only mode (API on http://127.0.0.1:3000)")

    logger.info("JARVIS is online. Systems nominal.")
    if voice_available:
        logger.info("Say 'Hey Jarvis' or use the Web UI.")
    else:
        logger.info("Web UI available at http://127.0.0.1:3000")
    logger.info("Press Ctrl+C to exit.")

    try:
        while _running:
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Shutting down JARVIS...")
        await proactive_engine.stop()
        await cognitive_orchestrator.stop()
        await workflow_monitor.stop()
        await app_monitor.stop()
        await system_monitor.stop()
        await event_bus.stop()
        jarvis_api.stop()
        logger.info("JARVIS offline. Goodbye.")


def run():
    """Synchronous entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
