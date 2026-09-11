"""Tests for goal orchestration: planner, verifier, and the bounded re-plan loop."""

import asyncio

from jarvis.brain.agent import JarvisAgent
from jarvis.brain.client import ChatResult
from jarvis.brain.goals import _parse_plan, plan_goal, verify_goal
from jarvis.tasks.store import TaskStore


class FakeClient:
    def __init__(self, script: list[ChatResult]) -> None:
        self.script = list(script)
        self.calls = 0

    async def chat(self, messages, tools=None) -> ChatResult:
        self.calls += 1
        if not self.script:
            return ChatResult("NONE", [], "stop")
        return self.script.pop(0)


def test_parse_plan_strips_numbering_and_bullets():
    assert _parse_plan("1. first\n- second\nthird\n\n") == ["first", "second", "third"]


async def _plan_and_verify():
    client = FakeClient([
        ChatResult("read data\nsummarize\nwrite report", [], "stop"),
        ChatResult("YES\nEvidence: report was written.", [], "stop"),
    ])
    plan = await plan_goal(client, "write a report")
    assert plan == ["read data", "summarize", "write report"]
    met, verdict = await verify_goal(client, "write a report", [{"role": "user", "content": "do it"}])
    assert met is True
    assert "report" in verdict


def test_plan_and_verify_round_trip():
    asyncio.run(_plan_and_verify())


def test_verify_goal_handles_unclear_response():
    client = FakeClient([
        ChatResult("Unclear whether this succeeded.", [], "stop"),
    ])
    met, verdict = asyncio.run(verify_goal(client, "write a report", [{"role": "user", "content": "do it"}]))
    assert met is False
    assert "Unclear" in verdict


def _agent(tmp_path, script, store) -> JarvisAgent:
    from jarvis.tools.base import ToolDefinition
    from jarvis.tools.executor import ToolExecutor
    from jarvis.tools.policy import RiskLevel
    from jarvis.tools.registry import ToolRegistry

    registry = ToolRegistry()

    async def add(a, b):
        return a + b

    registry.register(ToolDefinition("add", RiskLevel.SAFE, frozenset(), add))
    return JarvisAgent(ToolExecutor(registry), client=FakeClient(script), task_store=store)


def test_run_goal_replans_until_verified(tmp_path):
    # planner -> respond -> verifier(NO) -> planner -> respond -> verifier(YES)
    store = TaskStore(tmp_path / "tasks.db")
    agent = _agent(
        tmp_path,
        [
            ChatResult("compute the sum", [], "stop"),  # plan 1
            ChatResult("The sum is five, sir.", [], "stop"),  # answer 1
            ChatResult("NO\nNo evidence of output.", [], "stop"),  # verify 1
            ChatResult("compute and show the sum", [], "stop"),  # plan 2
            ChatResult("Two plus three is five, sir.", [], "stop"),  # answer 2
            ChatResult("YES\nSum shown.", [], "stop"),  # verify 2
        ],
        store,
    )
    reply = asyncio.run(agent.run_goal("add two and three", session_id="g1"))
    assert reply == "Two plus three is five, sir."
    assert store.get("g1")["status"] == "completed"


def test_run_goal_fails_after_replan_budget(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    agent = _agent(
        tmp_path,
        [
            ChatResult("compute", [], "stop"),
            ChatResult("five", [], "stop"),
            ChatResult("NO\nNot verified.", [], "stop"),
            ChatResult("compute", [], "stop"),
            ChatResult("five", [], "stop"),
            ChatResult("NO\nStill not verified.", [], "stop"),
            ChatResult("compute", [], "stop"),
            ChatResult("five", [], "stop"),
            ChatResult("NO\nNope.", [], "stop"),
        ],
        store,
    )
    asyncio.run(agent.run_goal("add two and three"))
    task = store.list_tasks()[0]
    assert task["status"] == "failed"
    assert task["plan"]
    assert task["steps"] == []


def test_run_goal_writes_lesson_to_memory(tmp_path):
    from jarvis.brain.memory import MemoryStore

    store = TaskStore(tmp_path / "tasks.db")
    agent = _agent(
        tmp_path,
        [
            ChatResult("compute the sum", [], "stop"),  # plan
            ChatResult("The sum is five, sir.", [], "stop"),  # answer
            ChatResult("YES\nSum shown.", [], "stop"),  # verify
            ChatResult("Use the add tool and report the result.", [], "stop"),  # reflect
        ],
        store,
    )
    agent.memory = MemoryStore(tmp_path / "memory.db")
    asyncio.run(agent.run_goal("add two and three", session_id="g2"))
    recalled = agent.memory.recall("add two and three")
    assert any(r.startswith("user: LESSON:") for r in recalled)