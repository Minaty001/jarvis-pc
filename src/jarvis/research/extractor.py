"""Web page content extraction, DOM sanitization, and article parsing for JARVIS PC."""

from __future__ import annotations

import html
import logging
import re
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


def sanitize_html(raw_html: str, max_chars: int = 8000) -> Dict[str, str]:
    """Clean raw HTML into clean readable text without ads, scripts, and navigation clutter."""
    if not raw_html:
        return {"title": "Untitled", "content": ""}

    # 1. Extract title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    title = html.unescape(title_match.group(1)).strip() if title_match else "Untitled Document"
    # Remove common title suffixes
    title = re.sub(r"\s*[-|–—]\s*.*$", "", title).strip() or "Untitled Document"

    # 2. Remove script, style, head, nav, footer, aside, form tags and comments
    text = re.sub(r"<!--.*?-->", "", raw_html, flags=re.DOTALL)
    text = re.sub(r"<(script|style|nav|footer|aside|header|noscript|iframe|svg|form)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # 3. Preserve structural breaks for headings and paragraphs
    text = re.sub(r"<(h[1-6]|p|div|li|tr)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # 4. Remove all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # 5. Unescape HTML entities
    text = html.unescape(text)

    # 6. Normalize whitespace
    lines = [line.strip() for line in text.splitlines()]
    clean_paragraphs = [line for line in lines if len(line) > 20]
    content = "\n\n".join(clean_paragraphs).strip()

    if len(content) > max_chars:
        content = content[:max_chars] + "\n... [Content truncated for synthesis]"

    return {
        "title": title,
        "content": content or "(No readable text extracted)",
    }


async def extract_article(url: str, max_chars: int = 8000) -> Dict[str, Any]:
    """Fetch URL and extract sanitized article content."""
    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        return {
            "success": False,
            "title": "Invalid URL",
            "url": clean_url,
            "content": f"Error: Invalid URL scheme '{clean_url}'",
            "length": 0,
        }

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(clean_url, headers=headers)
            if resp.status_code == 200:
                parsed = sanitize_html(resp.text, max_chars=max_chars)
                return {
                    "success": True,
                    "title": parsed["title"],
                    "url": clean_url,
                    "content": parsed["content"],
                    "length": len(parsed["content"]),
                }
            else:
                return {
                    "success": False,
                    "title": f"HTTP {resp.status_code}",
                    "url": clean_url,
                    "content": f"Failed to retrieve page: HTTP status {resp.status_code}",
                    "length": 0,
                }
    except Exception as exc:
        logger.debug("Article extraction error for '%s': %s", clean_url, exc)
        return {
            "success": False,
            "title": "Extraction Error",
            "url": clean_url,
            "content": f"Connection failed: {exc}",
            "length": 0,
        }
