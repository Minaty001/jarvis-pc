"""Web Search — Search the web."""

import httpx
from typing import Any

from config.logger import get_logger

logger = get_logger("tools.web_search")


async def web_search(query: str) -> dict[str, Any]:
    """Search the web using DuckDuckGo instant API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1},
            )
            data = resp.json()

            abstract = data.get("AbstractText", "")
            if abstract:
                return {"success": True, "result": abstract}

            topics = data.get("RelatedTopics", [])[:3]
            if topics:
                results = []
                for t in topics:
                    if isinstance(t, dict) and "Text" in t:
                        results.append(t["Text"])
                if results:
                    return {"success": True, "result": "\n".join(results)}

            return {"success": True, "result": f"Search results for '{query}' — try searching more specifically."}
    except Exception as e:
        return {"success": False, "result": f"Search failed: {e}"}
