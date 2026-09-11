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
    from jarvis.tools.builtin.coding import (
        git_branch,
        git_commit,
        git_diff,
        git_status,
        replace_file_snippet,
        run_workspace_tests,
    )
    from jarvis.tools.builtin.desktop_automation import (
        click_mouse,
        focus_window,
        locate_and_click,
        move_mouse,
        press_key,
        scroll_mouse,
        type_text,
    )
    from jarvis.tools.builtin.weather import get_daily_briefing, get_weather
    from jarvis.tools.builtin.voice_tools import (
        configure_wake_word,
        list_voice_profiles,
        set_voice_profile,
        toggle_auto_wake,
        tune_voice_acoustics,
    )
    from jarvis.tools.builtin.knowledge_tools import (
        ask_knowledge_base,
        get_knowledge_stats,
        index_knowledge_directory,
        search_knowledge,
    )
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
    registry.register(ToolDefinition(
        name="git_status",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"workspace.git"}),
        handler=git_status,
    ))
    registry.register(ToolDefinition(
        name="git_branch",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"workspace.git"}),
        handler=git_branch,
    ))
    registry.register(ToolDefinition(
        name="git_diff",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"workspace.git"}),
        handler=git_diff,
    ))
    registry.register(ToolDefinition(
        name="git_commit",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"workspace.git"}),
        handler=git_commit,
    ))
    registry.register(ToolDefinition(
        name="replace_file_snippet",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"filesystem.write"}),
        handler=replace_file_snippet,
    ))
    registry.register(ToolDefinition(
        name="run_workspace_tests",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"workspace.test"}),
        handler=run_workspace_tests,
    ))
    registry.register(ToolDefinition(
        name="click_mouse",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"desktop.input"}),
        handler=click_mouse,
    ))
    registry.register(ToolDefinition(
        name="move_mouse",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"desktop.input"}),
        handler=move_mouse,
    ))
    registry.register(ToolDefinition(
        name="type_text",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"desktop.input"}),
        handler=type_text,
    ))
    registry.register(ToolDefinition(
        name="press_key",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"desktop.input"}),
        handler=press_key,
    ))
    registry.register(ToolDefinition(
        name="focus_window",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"desktop.window"}),
        handler=focus_window,
    ))
    registry.register(ToolDefinition(
        name="scroll_mouse",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"desktop.input"}),
        handler=scroll_mouse,
    ))
    registry.register(ToolDefinition(
        name="locate_and_click",
        risk=RiskLevel.CONFIRM,
        capabilities=frozenset({"desktop.input", "media.vision"}),
        handler=locate_and_click,
    ))
    registry.register(ToolDefinition(
        name="get_weather",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"network.read"}),
        handler=get_weather,
    ))
    registry.register(ToolDefinition(
        name="get_daily_briefing",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"system.read", "network.read"}),
        handler=get_daily_briefing,
    ))
    registry.register(ToolDefinition(
        name="list_voice_profiles",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"voice.config"}),
        handler=list_voice_profiles,
    ))
    registry.register(ToolDefinition(
        name="set_voice_profile",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"voice.config"}),
        handler=set_voice_profile,
    ))
    registry.register(ToolDefinition(
        name="tune_voice_acoustics",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"voice.config"}),
        handler=tune_voice_acoustics,
    ))
    registry.register(ToolDefinition(
        name="toggle_auto_wake",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"voice.config"}),
        handler=toggle_auto_wake,
    ))
    registry.register(ToolDefinition(
        name="configure_wake_word",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"voice.config"}),
        handler=configure_wake_word,
    ))
    registry.register(ToolDefinition(
        name="search_knowledge",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"filesystem.read", "knowledge.search"}),
        handler=search_knowledge,
    ))
    registry.register(ToolDefinition(
        name="index_knowledge_directory",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"filesystem.read", "knowledge.index"}),
        handler=index_knowledge_directory,
    ))
    registry.register(ToolDefinition(
        name="ask_knowledge_base",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"filesystem.read", "knowledge.search"}),
        handler=ask_knowledge_base,
    ))
    registry.register(ToolDefinition(
        name="get_knowledge_stats",
        risk=RiskLevel.SAFE,
        capabilities=frozenset({"knowledge.search"}),
        handler=get_knowledge_stats,
    ))
