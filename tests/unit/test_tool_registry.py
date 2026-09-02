import pytest
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel

def test_tool_registry():
    registry = ToolRegistry()
    async def dummy(): pass
    tool = ToolDefinition("test_tool", RiskLevel.SAFE, frozenset(), dummy)
    registry.register(tool)
    assert registry.has("test_tool")
    assert registry.get("test_tool") == tool
    assert len(registry.list()) == 1

def test_duplicate_registration_raises():
    registry = ToolRegistry()
    async def dummy(): pass
    tool = ToolDefinition("test_tool", RiskLevel.SAFE, frozenset(), dummy)
    registry.register(tool)
    with pytest.raises(ValueError, match="duplicate tool"):
        registry.register(tool)
