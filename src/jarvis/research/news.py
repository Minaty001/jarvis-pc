"""Real-time RSS/Atom News Feed Aggregator for JARVIS PC."""

from __future__ import annotations

import html
import logging
import re
from typing import Any, Dict, List
import xml.etree.ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

# Curated high-signal RSS/Atom feed sources
_TOPIC_FEEDS = {
    "tech": [
        "https://news.ycombinator.com/rss",
        "https://feeds.arstechnica.com/arstechnica/index",
    ],
    "linux": [
        "https://www.phoronix.com/phoronix-rss.php",
        "https://www.omgubuntu.co.uk/feed",
    ],
    "ai": [
        "https://news.mit.edu/rss/topic/artificial-intelligence2",
        "https://rss.arxiv.org/rss/cs.AI",
    ],
    "science": [
        "https://www.sciencedaily.com/rss/top/science.xml",
        "https://phys.org/rss-feed/",
    ],
    "security": [
        "https://feeds.feedburner.com/TheHackersNews",
        "https://www.bleepingcomputer.com/feed/",
    ],
    "world": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
    ],
}


def _clean_xml_text(text: str | None) -> str:
    if not text:
        return ""
    # Strip CDATA and HTML tags
    clean = re.sub(r"<[^>]+>", "", text)
    return html.unescape(clean).strip()


async def fetch_news(topic: str = "tech", limit: int = 6) -> List[Dict[str, Any]]:
    """Fetch recent headlines and summaries for a topic from RSS feeds."""
    clean_topic = topic.strip().lower()
    feed_urls = _TOPIC_FEEDS.get(clean_topic, _TOPIC_FEEDS["tech"])

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, application/atom+xml, text/xml",
    }

    articles: List[Dict[str, Any]] = []

    for feed_url in feed_urls:
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(feed_url, headers=headers)
                if resp.status_code != 200:
                    continue

                root = ET.fromstring(resp.text)
                
                # Check for standard RSS <channel><item>
                items = root.findall(".//item")
                if not items:
                    # Check for Atom <entry>
                    items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

                for it in items:
                    title_elem = it.find("title")
                    if title_elem is None:
                        title_elem = it.find("{http://www.w3.org/2005/Atom}title")

                    link_elem = it.find("link")
                    if link_elem is None:
                        link_elem = it.find("{http://www.w3.org/2005/Atom}link")

                    desc_elem = it.find("description")
                    if desc_elem is None:
                        desc_elem = it.find("summary")
                    if desc_elem is None:
                        desc_elem = it.find("{http://www.w3.org/2005/Atom}summary")
                    if desc_elem is None:
                        desc_elem = it.find("{http://www.w3.org/2005/Atom}content")

                    date_elem = it.find("pubDate")
                    if date_elem is None:
                        date_elem = it.find("{http://www.w3.org/2005/Atom}updated")
                    if date_elem is None:
                        date_elem = it.find("{http://www.w3.org/2005/Atom}published")

                    title = _clean_xml_text(title_elem.text if title_elem is not None else None)
                    link = ""
                    if link_elem is not None:
                        link = link_elem.get("href") or link_elem.text or ""
                    link = link.strip()

                    desc = _clean_xml_text(desc_elem.text if desc_elem is not None else None)
                    if len(desc) > 200:
                        desc = desc[:200] + "..."

                    pub_date = _clean_xml_text(date_elem.text if date_elem is not None else None)

                    if title and link:
                        articles.append({
                            "title": title,
                            "url": link,
                            "summary": desc or "No summary available.",
                            "published": pub_date or "Recent",
                            "topic": clean_topic,
                        })

                    if len(articles) >= limit:
                        break

        except Exception as exc:
            logger.debug("Error fetching feed '%s': %s", feed_url, exc)

        if len(articles) >= limit:
            break

    return articles[:limit]
