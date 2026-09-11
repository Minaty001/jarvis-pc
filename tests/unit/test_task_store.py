"""Tests for the SQLite task store: persistence, fields, and agent resume."""

import asyncio

from jarvis.brain.agent import JarvisAgent
from jarvis.brain.client import ChatResult
from jarvis.tasks.store import TaskStore


def test_store_round_trip(tmp_path):
    path = tmp_path / "tasks.db"
    store = TaskStore(path)
    task_id = store.create(goal="write a report")
    store.set_plan(task_id, ["read data", "summarize"])
    store.set_status(task_id, "completed")

    task = TaskStore(path).get(task_id)
    assert task["goal"] == "write a report"
    assert task["plan"] == ["read data", "summarize"]
    assert task["status"] == "completed"


def test_store_create_is_idempotent(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    assert store.create(task_id="s1", goal="first") == "s1"
    assert store.create(task_id="s1", goal="second") == "s1"
    assert store.get("s1")["goal"] == "first"


def test_store_list_filters_by_status(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    a = store.create(goal="a")
    b = store.create(goal="b")
    store.set_status(b, "running")
    assert {t["id"] for t in store.list_tasks(status="open")} == {a}


def _agent(tmp_path, script, store) -> JarvisAgent:
    from jarvis.tools.base import ToolDefinition
    from jarvis.tools.executor import ToolExecutor
    from jarvis.tools.policy import RiskLevel
    from jarvis.tools.registry import ToolRegistry

    class FakeClient:
        def __init__(self, script):
            self.script = list(script)
            self.seen: list[list[dict]] = []

        async def chat(self, messages, tools=None):
            self.seen.append(list(messages))
            return self.script.pop(0)

    registry = ToolRegistry()

    async def add(a, b):
        return a + b

    registry.register(ToolDefinition("add", RiskLevel.SAFE, frozenset(), add))
    return JarvisAgent(
        ToolExecutor(registry),
        client=FakeClient(script),
        task_store=store,
    )


def test_agent_persists_turn_and_resumes(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    agent = _agent(tmp_path, [ChatResult("The sum is five, sir.", [], "stop")], store)
    asyncio.run(agent.respond("add two and three", session_id="s1"))

    task = store.get("s1")
    assert task["status"] == "completed"
    assert task["transcript"][0] == {"role": "user", "content": "add two and three"}
    assert task["transcript"][-1]["role"] == "assistant"

    # Fresh agent on the same session sees the persisted transcript (resume).
    agent2 = _agent(tmp_path, [ChatResult("Still five, sir.", [], "stop")], store)
    asyncio.run(agent2.respond("still five?", session_id="s1"))
    seen = agent2.client.seen[0]
    assert [m["role"] for m in seen] == ["system", "user", "assistant", "user"]
    assert seen[-1]["content"] == "still five?"