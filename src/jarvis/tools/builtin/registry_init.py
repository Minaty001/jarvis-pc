"""Single function that populates a ToolRegistry with all builtin tools."""
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel
from jarvis.tools.registry import ToolRegistry


def register_all_builtins(registry: ToolRegistry) -> None:
    """Register every builtin tool into the given registry."""
    from jarvis.tools.builtin.filesystem import SafeFileStore
    from jarvis.tools.builtin.applications import open_application
    from jarvis.tools.builtin.processes import find_processes
    from jarvis.tools.builtin.media import check_camera_permissions
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
