"""Tests for the JARVIS brain: persona, client, memory, and the agent loop."""

import pytest

from jarvis.brain.agent import JarvisAgent
from jarvis.brain.client import ChatResult, LLMClient, LocalBrain, ToolCall
from jarvis.brain.memory import MemoryStore
from jarvis.brain.persona import PERSONA, build_system_prompt


class FakeClient:
    """Scripted LLM client: returns pre-programmed results per call."""

    def __init__(self, script: list[ChatResult]) -> None:
        self.script = list(script)
        self.calls: list[list[dict]] = []

    async def chat(self, messages, tools=None) -> ChatResult:
        self.calls.append(list(messages))
        return self.script.pop(0)


# --- persona --------------------------------------------------------------

def test_persona_has_butler_register():
    assert "sir" in PERSONA
    assert "I am" in PERSONA
    assert "complete sentences" in PERSONA


def test_build_system_prompt_adds_tools_and_memories():
    prompt = build_system_prompt(memories="prior: user likes tea", tools="- read_file(user_path)")
    assert "Long-term memory" in prompt
    assert "- read_file(user_path)" in prompt
    assert "prior: user likes tea" in prompt


# --- client ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_local_brain_reply():
    result = await LocalBrain().chat([])
    assert result.content
    assert result.tool_calls == []


def test_placeholder_key_detection():
    assert LLMClient(api_key="your_key_here").available is False
    assert LLMClient(api_key="gsk_placeholder_here").available is False
    assert LLMClient(api_key="gsk_real_key_abc").available is True
    assert LLMClient(api_key=None).available is False


def test_client_reads_env_fallback(monkeypatch):
    monkeypatch.setenv("JARVIS_LLM_API_KEY", "sk-openai-key")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_your_key")
    client = LLMClient.from_settings()
    assert client.available is True


@pytest.mark.asyncio
async def test_client_retries_on_429_then_succeeds():
    import httpx

    from jarvis.brain.client import _chat_with_retry

    calls = {"n": 0}

    async def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        response = await _chat_with_retry(http, url="http://llm/x", headers={}, json={})
    assert response.status_code == 200
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_client_gives_up_on_persistent_429():
    import httpx

    from jarvis.brain.client import MAX_RETRIES, _chat_with_retry

    calls = {"n": 0}

    async def handler(request):
        calls["n"] += 1
        return httpx.Response(429, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(httpx.HTTPStatusError):
            await _chat_with_retry(http, url="http://llm/x", headers={}, json={})
    assert calls["n"] == MAX_RETRIES + 1


# --- memory ---------------------------------------------------------------

def test_memory_recall_ranks_by_overlap(tmp_path):
    store = MemoryStore(tmp_path / "mem.jsonl")
    store.add("what is my name", "Your name is Shanu, sir.")
    store.add("open the browser", "Opening Firefox, sir.")
    hits = store.recall("tell me my name")
    assert any("Shanu" in hit for hit in hits)
    assert len(hits) == 1


def test_memory_persists_across_instances(tmp_path):
    path = tmp_path / "mem.jsonl"
    MemoryStore(path).add("remember this", "Noted, sir.")
    hits = MemoryStore(path).recall("remember")
    assert hits[0].startswith("user: remember this")


# --- agent loop -----------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_executes_tool_then_answers():
    from jarvis.tools.executor import ToolExecutor
    from jarvis.tools.policy import RiskLevel
    from jarvis.tools.registry import ToolRegistry
    from jarvis.tools.base import ToolDefinition

    registry = ToolRegistry()

    async def add(a: int, b: int):
        return a + b

    registry.register(ToolDefinition("add", RiskLevel.SAFE, frozenset(), add))
    client = FakeClient([
        ChatResult(None, [ToolCall("c1", "add", {"a": 2, "b": 3})], "tool_calls"),
        ChatResult("The sum is five, sir.", [], "stop"),
    ])
    agent = JarvisAgent(ToolExecutor(registry), client=client)
    reply = await agent.respond("add two and three")
    assert reply == "The sum is five, sir."
    tool_msg = next(m for m in client.calls[1] if m["role"] == "tool")
    assert "observation (add): 5" in tool_msg["content"]


@pytest.mark.asyncio
async def test_agent_confirmation_denied():
    from jarvis.tools.base import ToolDefinition
    from jarvis.tools.executor import ToolExecutor
    from jarvis.tools.policy import RiskLevel
    from jarvis.tools.registry import ToolRegistry

    registry = ToolRegistry()

    async def risky():
        return "done"

    registry.register(ToolDefinition("risky", RiskLevel.CONFIRM, frozenset(), risky))
    client = FakeClient([
        ChatResult(None, [ToolCall("c1", "risky", {})], "tool_calls"),
        ChatResult("I shall not proceed, sir.", [], "stop"),
    ])
    agent = JarvisAgent(
        ToolExecutor(registry, confirmation_secret="sec"),
        client=client,
        confirmation_secret="sec",
    )
    reply = await agent.respond("do the risky thing", session_id="s1")
    assert reply == "I shall not proceed, sir."
    tool_msg = next(m for m in client.calls[1] if m["role"] == "tool")
    assert "approval required and was not granted" in tool_msg["content"]


@pytest.mark.asyncio
async def test_agent_confirmation_approved():
    from jarvis.tools.base import ToolDefinition
    from jarvis.tools.confirmation import create_confirmation_token
    from jarvis.tools.executor import ToolExecutor
    from jarvis.tools.policy import RiskLevel
    from jarvis.tools.registry import ToolRegistry

    registry = ToolRegistry()

    async def risky():
        return "done"

    registry.register(ToolDefinition("risky", RiskLevel.CONFIRM, frozenset(), risky))
    client = FakeClient([
        ChatResult(None, [ToolCall("c1", "risky", {})], "tool_calls"),
        ChatResult("It is done, sir.", [], "stop"),
    ])

    async def resolver(tool_name, args):
        return create_confirmation_token(tool_name, args, "s1", "sec")

    agent = JarvisAgent(
        ToolExecutor(registry, confirmation_secret="sec"),
        client=client,
        confirmation_secret="sec",
        confirmation_resolver=resolver,
    )
    reply = await agent.respond("proceed", session_id="s1")
    assert reply == "It is done, sir."
    tool_msg = next(m for m in client.calls[1] if m["role"] == "tool")
    assert "observation (risky): done" in tool_msg["content"]


@pytest.mark.asyncio
async def test_agent_confirmation_token_rejected_on_wrong_session():
    from jarvis.tools.base import ToolDefinition
    from jarvis.tools.confirmation import create_confirmation_token
    from jarvis.tools.executor import ToolExecutor
    from jarvis.tools.policy import RiskLevel
    from jarvis.tools.registry import ToolRegistry

    registry = ToolRegistry()

    async def risky():
        return "done"

    registry.register(ToolDefinition("risky", RiskLevel.CONFIRM, frozenset(), risky))
    client = FakeClient([
        ChatResult(None, [ToolCall("c1", "risky", {})], "tool_calls"),
        ChatResult("Denied, sir.", [], "stop"),
    ])

    # Resolver mints for session "cli" but the request runs in "s1" -> rejected.
    async def resolver(tool_name, args):
        return create_confirmation_token(tool_name, args, "cli", "sec")

    agent = JarvisAgent(
        ToolExecutor(registry, confirmation_secret="sec"),
        client=client,
        confirmation_secret="sec",
        confirmation_resolver=resolver,
    )
    await agent.respond("do it", session_id="s1")
    tool_msg = next(m for m in client.calls[1] if m["role"] == "tool")
    assert "tool failed" in tool_msg["content"]

def test_memory_migrates_existing_jsonl(tmp_path):
    path = tmp_path / "mem.jsonl"
    path.write_text('{"ts": 1, "user": "old episode", "reply": "Old reply, sir."}\n', encoding="utf-8")
    hits = MemoryStore(path).recall("old")
    assert hits and hits[0].startswith("user: old episode")


def test_memory_trims_to_cap(tmp_path):
    store = MemoryStore(tmp_path / "mem.db")
    for i in range(510):
        store.add(f"urn{i}zz", f"repl{i}yy")
    assert store.recall("urn500zz")
    assert store.recall("urn0zz") == []


def test_memory_recall_with_special_characters_and_quotes(tmp_path):
    store = MemoryStore(tmp_path / "mem.db")
    store.add('play "song title"', "playing song")
    hits = store.recall('play "song title"')
    assert hits and "playing song" in hits[0]
