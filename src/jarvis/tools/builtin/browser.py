"""CDP-based browser tool: headless Chrome + DOM query over the DevTools protocol.

Launches headless Chrome with --remote-debugging-port, finds the page target's
WebSocket URL, and reads the rendered DOM text via Runtime.evaluate. No vision,
no screenshots — the plan's "DOM selectors, cheap" route. Each call uses an
ephemeral Chrome instance and tears it down afterwards.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import socket
import subprocess  # nosec B404 B603
import tempfile
import time

import websockets

_CHROME_BIN = "/usr/bin/google-chrome"
_ALLOWED_URL_SCHEMES = ("http", "https")
MAX_TEXT = 6000
_NAVIGATE_WAIT_S = 3.0


def _pick_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def _page_ws_url(port: int, timeout_s: float = 10.0) -> str:
    """Poll /json until Chrome exposes a page target; return its WS debugger URL."""
    deadline = time.monotonic() + timeout_s
    import urllib.request

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(  # nosec B310 - localhost
                f"http://127.0.0.1:{port}/json", timeout=1
            ) as response:
                targets = json.loads(response.read())
            page = next((t for t in targets if t.get("type") == "page"), None)
            if page and page.get("webSocketDebuggerUrl"):
                return page["webSocketDebuggerUrl"]
        except OSError:
            pass
        await asyncio.sleep(0.1)
    raise RuntimeError("Chrome CDP endpoint not reachable on port %d" % port)


async def _runtime_eval(ws_url: str, expression: str) -> str:
    async with websockets.connect(ws_url) as ws:
        await ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expression, "returnByValue": True},
                }
            )
        )
        while True:
            message = json.loads(await ws.recv())
            if message.get("id") == 1:
                return str(message.get("result", {}).get("result", {}).get("value", ""))


async def browse_web(url: str) -> str:
    """Fetch `url` and return the rendered page's visible text + title."""
    scheme = url.strip().split(":", 1)[0].lower()
    if scheme not in _ALLOWED_URL_SCHEMES:
        raise ValueError(f"unsupported URL scheme {scheme!r}")

    port = _pick_port()
    profile = tempfile.mkdtemp(prefix="jarvis-chrome-")
    process = subprocess.Popen(  # nosec B603 B607
        [
            _CHROME_BIN,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-extensions",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ws_url = await _page_ws_url(port)
        await asyncio.sleep(_NAVIGATE_WAIT_S)
        title = await _runtime_eval(ws_url, "document.title")
        text = await _runtime_eval(ws_url, "document.body ? document.body.innerText : ''")
        body = text.strip()[:MAX_TEXT] or "(no visible text)"
        return f"title: {title}\n\n{body}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(profile, ignore_errors=True)