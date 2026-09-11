"""Telegram bridge: phone access to JARVIS through the authenticated HTTP gateway.

Long-polls Telegram's getUpdates (no webhook, works behind NAT) and forwards every
text message to the local /chat endpoint with the API token, then sends the reply
back. One bridge per JARVIS instance. Requires JARVIS_TELEGRAM_TOKEN and a
JARVIS_TELEGRAM_ALLOWED_CHATS allow-list of numeric chat ids.
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_TG_API = "https://api.telegram.org/bot{token}"


def allowed_chats(raw: str | None) -> set[int]:
    """Parse a comma/space separated allow-list of Telegram chat ids."""
    if not raw:
        return set()
    result: set[int] = set()
    for part in raw.replace(",", " ").split():
        try:
            result.add(int(part))
        except ValueError:
            logger.warning("ignoring non-numeric Telegram chat id %r", part)
    return result


async def run_bridge(gateway_url: str, api_token: str, tg_token: str, allow: set[int]) -> None:
    """Poll Telegram and proxy messages through `gateway_url`/chat forever."""
    if not tg_token:
        raise SystemExit("JARVIS_TELEGRAM_TOKEN is required for the bridge")
    if not api_token:
        raise SystemExit("JARVIS_API_TOKEN is required so the bridge can authenticate to the gateway")
    offset: int = 0
    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            try:
                updates = await client.get(
                    f"{_TG_API.format(token=tg_token)}/getUpdates",
                    params={"timeout": 25, "offset": offset},
                )
                updates.raise_for_status()
                for update in updates.json().get("result", []):
                    offset = int(update["update_id"]) + 1
                    await _handle_update(client, tg_token, allow, gateway_url, api_token, update)
            except Exception as exc:
                logger.warning("Telegram polling error: %s — retrying in 5s", exc)
                await asyncio.sleep(5)


async def _handle_update(
    client: httpx.AsyncClient,
    tg_token: str,
    allow: set[int],
    gateway_url: str,
    api_token: str,
    update: dict,
) -> None:
    message = update.get("message") or {}
    text = (message.get("text") or "").strip()
    chat_id = (message.get("chat") or {}).get("id")
    if not text or chat_id is None:
        return
    if chat_id not in allow:
        await _send(client, tg_token, chat_id, "This chat is not authorized to use JARVIS.")
        return
    reply = await _forward(client, gateway_url, api_token, chat_id, text)
    await _send(client, tg_token, chat_id, reply)


async def _forward(client: httpx.AsyncClient, gateway_url: str, api_token: str, chat_id: int, text: str) -> str:
    try:
        resp = await client.post(
            f"{gateway_url.rstrip('/')}/chat",
            headers={"Authorization": f"Bearer {api_token}"},
            json={"message": text, "session_id": f"telegram-{chat_id}"},
        )
        resp.raise_for_status()
        return resp.json().get("reply", "(no reply)")
    except Exception as exc:  # keep the bridge alive; surface the error to the user
        return f"JARVIS gateway error: {exc}"


async def _send(client: httpx.AsyncClient, tg_token: str, chat_id: int, text: str) -> None:
    try:
        resp = await client.post(
            f"{_TG_API.format(token=tg_token)}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Failed to send Telegram message to chat %s: %s", chat_id, exc)


def bridge_main(gateway_url: str | None = None) -> None:
    """Entrypoint for `jarvis telegram`: load settings and run the bridge."""
    from jarvis.config.settings import get_settings

    settings = get_settings()
    url = gateway_url or f"http://{settings.host}:{settings.port}"
    asyncio.run(
        run_bridge(
            gateway_url=url,
            api_token=settings.api_token or os.getenv("JARVIS_API_TOKEN", ""),
            tg_token=settings.telegram_token or os.getenv("JARVIS_TELEGRAM_TOKEN", ""),
            allow=allowed_chats(settings.telegram_allowed_chats or os.getenv("JARVIS_TELEGRAM_ALLOWED_CHATS")),
        )
    )