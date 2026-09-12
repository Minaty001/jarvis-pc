"""Web and online actions: Search Google, Open URLs, Browse YouTube."""

from __future__ import annotations

import urllib.parse
import webbrowser
from typing import Any

from .base import ActionResult, BaseAction


class WebSearchAction(BaseAction):
    """Performs a web search in the default browser."""
    name = "web_search"
    description = "Search Google, YouTube, or the web for a given query."
    patterns = [
        r"(?:search|google|look\s+up)\s+(?:for\s+)?(?P<query>.+?)(?:\s+on\s+(?P<engine>google|youtube|bing))?$",
        r"search\s+(?P<engine>google|youtube|bing)\s+for\s+(?P<query>.+)$",
    ]

    def execute(self, query: str = "", engine: str | None = None, **kwargs: Any) -> ActionResult:
        clean_query = query.strip()
        if not clean_query:
            return ActionResult(success=False, message="No search query provided.")

        engine_name = (engine or "google").lower()
        if engine_name == "youtube":
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(clean_query)}"
            target = "YouTube"
        elif engine_name == "bing":
            url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(clean_query)}"
            target = "Bing"
        else:
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(clean_query)}"
            target = "Google"

        try:
            webbrowser.open(url)
            return ActionResult(success=True, message=f"Searching {target} for '{clean_query}'.", data={"query": clean_query, "url": url})
        except Exception as err:
            return ActionResult(success=False, message=f"Failed to search: {err}")


class OpenUrlAction(BaseAction):
    """Opens a website URL directly."""
    name = "open_url"
    description = "Open a specific website or domain in the browser."
    patterns = [
        r"(?:open|go\s+to|visit)\s+(?:website\s+)?(?P<url>https?://[^\s]+|[a-zA-Z0-9_\-]+\.(?:com|org|io|net|edu|dev|ai|app)(?:/[^\s]*)?)",
        r"(?:open|go\s+to)\s+(?P<site>youtube|github|google|reddit|twitter|wikipedia|gmail)$",
    ]

    SITE_MAP = {
        "youtube": "https://www.youtube.com",
        "github": "https://www.github.com",
        "google": "https://www.google.com",
        "reddit": "https://www.reddit.com",
        "twitter": "https://www.x.com",
        "wikipedia": "https://www.wikipedia.org",
        "gmail": "https://mail.google.com",
    }

    def execute(self, url: str | None = None, site: str | None = None, **kwargs: Any) -> ActionResult:
        target_url = None
        if site and site.lower() in self.SITE_MAP:
            target_url = self.SITE_MAP[site.lower()]
        elif url:
            target_url = url if url.startswith(("http://", "https://")) else f"https://{url}"

        if not target_url:
            return ActionResult(success=False, message="Invalid URL or website name.")

        try:
            webbrowser.open(target_url)
            return ActionResult(success=True, message=f"Opening {target_url}.", data={"url": target_url})
        except Exception as err:
            return ActionResult(success=False, message=f"Failed to open URL: {err}")
