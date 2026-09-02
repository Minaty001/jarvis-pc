import pytest
from jarvis.tools.base import ToolDefinition
from jarvis.tools.policy import RiskLevel


def test_tool_definition_immutable():
    async def dummy():
        pass

    tool = ToolDefinition(
        name="read_file",
        risk=RiskLevel.SAFE,
        capabilities=frozenset(["filesystem.read"]),
        handler=dummy,
    )
    assert tool.name == "read_file"
    assert tool.risk == RiskLevel.SAFE
    assert "filesystem.read" in tool.capabilities
    assert tool.handler == dummy

    with pytest.raises((AttributeError, TypeError)):
        tool.name = "write_file"
