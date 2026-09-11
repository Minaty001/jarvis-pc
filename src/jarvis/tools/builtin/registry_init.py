"""Single function that populates a ToolRegistry with all builtin tools."""
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel
from jarvis.tools.registry import ToolRegistry


def register_all_builtins(registry: ToolRegistry) -> None:
    """Register every builtin tool into the given registry."""
    from jarvis.tools.builtin.filesystem import SafeFileStore
    from jarvis.tools.builtin.applications import open_application, open_url
    from jarvis.tools.builtin.processes import find_processes
    from jarvis.tools.builtin.media import check_camera_permissions, play_song
    from jarvis.tools.builtin.camera import list_cameras, take_photo
    from jarvis.tools.builtin.screen import take_screenshot, get_active_window, list_open_windows
    from jarvis.tools.builtin.vision import analyze_image
    from jarvis.tools.builtin.browser import browse_web
    from pathlib import Path

    # Create a default file store rooted at user home
    _store = SafeFileStore(Path.home())

    registry.register(ToolDefinition(
        name="read_file",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"filesystem.read"}),
        handler=_store.read_text,
    ))
    registry.register(ToolDefinition(
        name="write_file",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"filesystem.write"}),
        handler=_store.write_text,
    ))
    registry.register(ToolDefinition(
        name="open_application",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"desktop.applications"}),
        handler=open_application,
    ))
    registry.register(ToolDefinition(
        name="open_url",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"desktop.applications"}),
        handler=open_url,
    ))
    registry.register(ToolDefinition(
        name="find_processes",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"system.read"}),
        handler=find_processes,
    ))
    registry.register(ToolDefinition(
        name="check_camera",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"media.camera"}),
        handler=check_camera_permissions,
    ))
    registry.register(ToolDefinition(
        name="list_cameras",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"media.camera"}),
        handler=list_cameras,
    ))
    registry.register(ToolDefinition(
        name="take_photo",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"media.camera"}),
        handler=take_photo,
    ))
    registry.register(ToolDefinition(
        name="take_screenshot",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"desktop.screen"}),
        handler=take_screenshot,
    ))
    registry.register(ToolDefinition(
        name="get_active_window",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"system.read"}),
        handler=get_active_window,
    ))
    registry.register(ToolDefinition(
        name="list_open_windows",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"system.read"}),
        handler=list_open_windows,
    ))
    registry.register(ToolDefinition(
        name="analyze_image",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"media.vision"}),
        handler=analyze_image,
    ))
    registry.register(ToolDefinition(
        name="play_song",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"media.playback"}),
        handler=play_song,
    ))
    registry.register(ToolDefinition(
        name="browse_web",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"network.read"}),
        handler=browse_web,
    ))
