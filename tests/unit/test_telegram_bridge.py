"""Unit tests for the Telegram bridge."""

import httpx
import pytest

from jarvis.remote.telegram import _handle_update, allowed_chats


def _transport(gateway_reply: str = "At your service, sir."):
    """MockTransport routing /sendMessage to Telegram and /chat to the local gateway."""
    calls = {"gateway": [], "telegram": []}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/chat"):
            calls["gateway"].append(request)
            return httpx.Response(200, json={"reply": gateway_reply})
        calls["telegram"].append(request)
        return httpx.Response(200, json={"ok": True})

    return httpx.MockTransport(handler), calls


@pytest.mark.parametrize("raw,expected", [
    ("123", {123}),
    ("123, 456 789", {123, 456, 789}),
    ("abc,12", {12}),
    (None, set()),
])
def test_allowed_chats_parses(raw, expected):
    assert allowed_chats(raw) == expected


@pytest.mark.asyncio
async def test_handle_update_forwards_to_gateway_and_sends_reply():
    transport, calls = _transport()
    async with httpx.AsyncClient(transport=transport) as client:
        await _handle_update(client, "tg-tok", {123}, "http://127.0.0.1:8000", "tok",
                             {"message": {"chat": {"id": 123}, "text": "hello"}})
    assert len(calls["gateway"]) == 1
    body = calls["gateway"][0].content.decode()
    assert '"message":"hello"' in body
    assert "Bearer tok" in calls["gateway"][0].headers["authorization"]
    assert len(calls["telegram"]) == 1


@pytest.mark.asyncio
async def test_handle_update_denies_unlisted_chat():
    transport, calls = _transport()
    async with httpx.AsyncClient(transport=transport) as client:
        await _handle_update(client, "tg-tok", {123}, "http://127.0.0.1:8000", "tok",
                             {"message": {"chat": {"id": 999}, "text": "hello"}})
    assert calls["gateway"] == []
    assert len(calls["telegram"]) == 1  # denied notice only