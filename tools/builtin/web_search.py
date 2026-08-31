"""Web Search — Search the web and open search results in browser."""

import subprocess
import urllib.parse
from typing import Any
import httpx

from config.logger import get_logger

logger = get_logger("tools.web_search")

URL_SHORTCUTS = {
    "github trending": "https://github.com/trending",
    "github": "https://github.com",
    "google": "https://google.com",
    "gmail": "https://mail.google.com",
    "twitter": "https://x.com",
    "reddit": "https://reddit.com",
    "news": "https://news.google.com",
}


async def web_search(query: str) -> dict[str, Any]:
    """Search the web and open results in browser."""
    if not query or not query.strip():
        return {"success": False, "result": "No search query provided"}

    clean_query = query.strip()
    query_lower = clean_query.lower()

    # Determine target URL
    target_url = None
    for key, url in URL_SHORTCUTS.items():
        if key in query_lower:
            target_url = url
            break

    if not target_url:
        target_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(clean_query)}"

    # Open browser window
    msg = f"Opened '{clean_query}' in browser ({target_url})"
    try:
        subprocess.Popen(["xdg-open", target_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info(msg)
    except Exception as e:
        logger.warning("Could not open browser for search: %s", e)

    # Fetch instant summary if available
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": clean_query, "format": "json", "no_html": 1},
            )
            data = resp.json()
            abstract = data.get("AbstractText", "")
            if abstract:
                return {"success": True, "result": f"{msg}\nSummary: {abstract}"}
    except Exception:
        pass

    return {"success": True, "result": msg}
