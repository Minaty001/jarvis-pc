import pytest
from jarvis.actions import (
    ActionRegistry,
    ActionResult,
    DateAction,
    NotifyAction,
    OpenAppAction,
    OpenUrlAction,
    ScreenshotAction,
    SystemStatsAction,
    TimeAction,
    VolumeAction,
    WebSearchAction,
)


def test_registry_initialization():
    registry = ActionRegistry()
    actions = registry.all_actions()
    assert len(actions) >= 10
    assert registry.get("set_volume") is not None
    assert registry.get("open_app") is not None
    assert registry.get("web_search") is not None
    assert registry.get("tell_time") is not None


def test_time_action():
    action = TimeAction()
    res = action.execute()
    assert res.success is True
    assert "It is" in res.message


def test_date_action():
    action = DateAction()
    res = action.execute()
    assert res.success is True
    assert "Today is" in res.message


def test_system_stats_action():
    action = SystemStatsAction()
    res = action.execute()
    assert res.success is True
    assert "CPU at" in res.message
    assert "Memory at" in res.message


def test_volume_action():
    action = VolumeAction()
    res = action.execute(level=50)
    assert res.success is True
    assert "50 percent" in res.message


def test_web_search_action():
    action = WebSearchAction()
    res = action.execute(query="python programming", engine="google")
    assert res.success is True
    assert "Searching Google for 'python programming'" in res.message


def test_open_url_action():
    action = OpenUrlAction()
    res = action.execute(site="github")
    assert res.success is True
    assert "github.com" in res.data["url"]
