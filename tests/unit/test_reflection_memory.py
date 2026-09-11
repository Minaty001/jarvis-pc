"""Unit tests for SQLite FTS5 reflection storage and BM25 recall."""

from jarvis.brain.memory import MemoryStore


def test_store_and_recall_reflection(tmp_path):
    db_path = tmp_path / "test_memory.db"
    store = MemoryStore(db_path)

    # 1. Store a reflection
    ref_id = store.store_reflection(
        goal_query="find running firefox process",
        lesson="Use find_processes with 'firefox' substring instead of broad ps queries.",
        category="tool_usage",
        recipe=["find_processes(name='firefox')"],
        verified=True,
    )
    assert ref_id > 0

    # 2. Recall matching reflection
    recalled = store.recall_reflections("check if firefox is running", limit=2)
    assert len(recalled) == 1
    assert recalled[0]["category"] == "tool_usage"
    assert "find_processes" in recalled[0]["lesson"]
    assert recalled[0]["verified"] is True
    assert recalled[0]["success_count"] == 1

    # 3. Store duplicate - should increment success_count rather than duplicate row
    store.store_reflection(
        goal_query="find running firefox process",
        lesson="Use find_processes with 'firefox' substring instead of broad ps queries.",
        category="tool_usage",
        recipe=["find_processes(name='firefox')"],
        verified=True,
    )
    all_refs = store.list_reflections()
    assert len(all_refs) == 1
    assert all_refs[0]["success_count"] == 2

    # 4. Unrelated query returns empty
    unrelated = store.recall_reflections("bake a chocolate cake")
    assert len(unrelated) == 0

    store.close()


def test_list_reflections(tmp_path):
    db_path = tmp_path / "test_memory.db"
    store = MemoryStore(db_path)

    store.store_reflection(goal_query="goal 1", lesson="lesson 1", category="cat1", verified=True)
    store.store_reflection(goal_query="goal 2", lesson="lesson 2", category="cat2", verified=False)

    recent = store.list_reflections(limit=5)
    assert len(recent) == 2
    assert recent[0]["goal_query"] == "goal 2"
    assert recent[0]["failure_count"] == 1
    assert recent[1]["goal_query"] == "goal 1"
    assert recent[1]["success_count"] == 1

    store.close()
