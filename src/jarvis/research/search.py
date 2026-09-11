"""Multi-backend web search client (DuckDuckGo and Wikipedia) for JARVIS PC."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)


async def search_web(query: str, limit: int = 5) -> List[Dict[str, str]]:
    """Search the web via DuckDuckGo HTML parser and return top results."""
    clean_query = query.strip()
    if not clean_query:
        return []

    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(clean_query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    results: List[Dict[str, str]] = []
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                html = resp.text
                # Extract results: class="result__title" and class="result__snippet"
                # DuckDuckGo HTML link format: <a class="result__url" href="..."> or <a class="result__snippet" ...>
                title_matches = re.findall(
                    r'<a[^>]+class="result__snippet"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                    html,
                    re.DOTALL | re.IGNORECASE,
                )
                
                # Alternate pattern for standard result links
                std_matches = re.findall(
                    r'<a[^>]+class="result__url"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                    html,
                    re.DOTALL | re.IGNORECASE,
                )

                # Fallback broad match
                all_links = re.findall(
                    r'<h2[^>]*class="result__title"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?</h2>.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                    html,
                    re.DOTALL | re.IGNORECASE,
                )

                for link, title_raw, snippet_raw in all_links[:limit]:
                    # Unescape duckduckgo redirect link if present (e.g. /l/?kh=-1&uddg=http%3A%2F%2F...)
                    final_url = link
                    if "uddg=" in link:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                        if "uddg" in parsed:
                            final_url = parsed["uddg"][0]

                    clean_title = re.sub(r"<[^>]+>", "", title_raw).strip()
                    clean_snippet = re.sub(r"<[^>]+>", "", snippet_raw).strip()

                    if clean_title and final_url.startswith("http"):
                        results.append({
                            "title": clean_title,
                            "url": final_url,
                            "snippet": clean_snippet,
                        })

    except Exception as exc:
        logger.debug("DuckDuckGo search error (%s); trying fallback", exc)

    # If DuckDuckGo returned nothing, supplement with Wikipedia
    if not results:
        wiki_results = await search_wikipedia(clean_query, limit=limit)
        results.extend(wiki_results)

    return results[:limit]


async def search_wikipedia(query: str, limit: int = 3) -> List[Dict[str, str]]:
    """Query Wikipedia OpenSearch API for encyclopedic summaries."""
    clean_query = query.strip()
    if not clean_query:
        return []

    encoded = urllib.parse.quote(clean_query)
    url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={encoded}&limit={limit}&namespace=0&format=json"

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(url, headers={"User-Agent": "JarvisAssistant/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) >= 4:
                    titles = data[1]
                    snippets = data[2]
                    urls = data[3]
                    results = []
                    for t, s, u in zip(titles, snippets, urls):
                        if t and u:
                            results.append({
                                "title": f"Wikipedia: {t}",
                                "url": u,
                                "snippet": s or "Encyclopedia entry.",
                            })
                    return results
    except Exception as exc:
        logger.debug("Wikipedia search error: %s", exc)

    return []
