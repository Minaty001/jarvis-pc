"""Tests for Long-Term Semantic Memory, User Profile Knowledge Graph, Tools, and CLI."""

from unittest.mock import MagicMock, patch
import pytest

from jarvis.brain.memory import MemoryStore
from jarvis.brain.persona import build_system_prompt
from jarvis.cli.main import run_cli
from jarvis.tools.builtin.memory_tools import (
    forget_fact,
    get_user_profile,
    recall_facts,
    remember_fact,
)


@pytest.fixture
def temp_memory_store(tmp_path):
    db_file = tmp_path / "memory.db"
    return MemoryStore(db_file)


def test_facts_crud_and_user_profile_sync(temp_memory_store):
    store = temp_memory_store

    # 1. Store user preference
    fid1 = store.store_fact(
        key="editor",
        value="VS Code",
        category="tools",
        subject="user",
        predicate="preference",
    )
    assert fid1 > 0

    # 2. Store personal identity
    fid2 = store.store_fact(
        key="name",
        value="Shanu",
        category="personal",
        subject="user",
        predicate="identity",
    )
    assert fid2 > 0

    # Verify user profile table kept in sync
    profile = store.get_user_profile()
    assert "tools" in profile
    assert profile["tools"]["editor"] == "VS Code"
    assert "personal" in profile
    assert profile["personal"]["name"] == "Shanu"

    # 3. Update existing fact
    fid3 = store.store_fact(
        key="editor",
        value="Neovim",
        category="tools",
        subject="user",
        predicate="preference",
    )
    assert fid3 == fid1

    profile_updated = store.get_user_profile()
    assert profile_updated["tools"]["editor"] == "Neovim"

    # 4. List facts
    facts = store.list_facts()
    assert len(facts) == 2
    keys = [f["key"] for f in facts]
    assert "editor" in keys
    assert "name" in keys

    # 5. Delete fact
    assert store.delete_fact("name") is True
    profile_after = store.get_user_profile()
    assert "name" not in profile_after.get("personal", {})
    assert len(store.list_facts()) == 1


def test_semantic_bm25_fact_recall(temp_memory_store):
    store = temp_memory_store

    store.store_fact(key="favorite_framework", value="FastAPI and PyTorch", category="preference")
    store.store_fact(key="operating_system", value="Linux Mint 22 Cinnamon", category="hardware")
    store.store_fact(key="project_phoenix", value="Rust high throughput gateway", category="work", subject="project_phoenix")

    # Recall by topic
    fastapi_matches = store.recall_facts("FastAPI framework")
    assert len(fastapi_matches) >= 1
    assert fastapi_matches[0]["key"] == "favorite_framework"

    os_matches = store.recall_facts("Linux Mint Cinnamon")
    assert len(os_matches) >= 1
    assert os_matches[0]["key"] == "operating_system"

    # Recall with category filter
    filtered = store.recall_facts("Rust", category="work")
    assert len(filtered) == 1
    assert filtered[0]["key"] == "project_phoenix"


def test_memory_summary_metrics(temp_memory_store):
    store = temp_memory_store
    store.add("Hello", "Greetings, sir.")
    store.store_reflection(goal_query="Find git branch", lesson="Use git branch --show-current")
    store.store_fact(key="theme", value="dark", category="ui")

    summary = store.get_memory_summary()
    assert summary["episodes_count"] == 1
    assert summary["reflections_count"] == 1
    assert summary["facts_count"] == 1
    assert summary["profile_keys_count"] == 1


def test_build_system_prompt_with_profile_and_facts():
    prompt = build_system_prompt(
        user_profile={"tools": {"editor": "VS Code"}, "personal": {"name": "Shanu"}},
        facts=[{"subject": "user", "predicate": "preference", "key": "theme", "value": "cyan HUD"}],
        memories="user: status | jarvis: nominal",
    )

    assert "## Operator Profile & Preferences" in prompt
    assert "editor: VS Code" in prompt
    assert "name: Shanu" in prompt
    assert "## Relevant Long-Term Knowledge & Facts" in prompt
    assert "theme: cyan HUD" in prompt
    assert "## Long-term memory (from prior sessions)" in prompt


def test_builtin_memory_tools(tmp_path):
    db_file = tmp_path / "memory.db"
    mock_store = MemoryStore(db_file)

    with patch("jarvis.tools.builtin.memory_tools._get_memory_store", return_value=mock_store):
        # 1. remember_fact
        res1 = remember_fact("music_genre", "Synthwave", category="preference")
        assert "Memorized [preference]" in res1
        assert "music_genre" in res1

        # 2. recall_facts
        res2 = recall_facts("Synthwave music")
        assert "Recalled 1 memory record(s)" in res2
        assert "music_genre: Synthwave" in res2

        # 3. get_user_profile
        res3 = get_user_profile()
        assert "JARVIS Operator Profile" in res3
        assert "music_genre" in res3

        # 4. forget_fact
        res4 = forget_fact("music_genre")
        assert "Successfully removed fact" in res4

        res5 = recall_facts("Synthwave")
        assert "No matching memories found" in res5


def test_cli_memory_subcommands(tmp_path, capsys):
    db_file = tmp_path / "memory.db"
    mock_store = MemoryStore(db_file)

    with patch("jarvis.brain.memory.MemoryStore", return_value=mock_store):
        # Remember
        ret = run_cli(["memory", "remember", "editor", "PyCharm", "--category", "tools"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Memorized [tools] 'editor': 'PyCharm'" in captured.out

        # List
        ret = run_cli(["memory", "list"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "editor" in captured.out
        assert "PyCharm" in captured.out

        # Profile
        ret = run_cli(["memory", "profile"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "TOOLS" in captured.out
        assert "editor" in captured.out

        # Search
        ret = run_cli(["memory", "search", "PyCharm"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "editor" in captured.out

        # Stats
        ret = run_cli(["memory", "stats"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Semantic Facts & Knowledge: 1" in captured.out

        # Forget
        ret = run_cli(["memory", "forget", "editor"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Successfully deleted memory 'editor'" in captured.out
