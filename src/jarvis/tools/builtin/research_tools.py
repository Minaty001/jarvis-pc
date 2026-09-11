"""Builtin agent tools for Autonomous Web Research, Article Extraction & Live News."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from jarvis.research.engine import get_research_engine
from jarvis.research.extractor import extract_article
from jarvis.research.news import fetch_news

logger = logging.getLogger(__name__)


async def deep_web_research(query: str) -> str:
    """Perform autonomous multi-source web investigation and factual synthesis with citations."""
    engine = get_research_engine()
    res = await engine.research_topic(query)
    summary = res["summary"]
    sources = res["sources"]

    source_lines = [f"\nVerified References ({len(sources)} sources):"]
    for s in sources:
        source_lines.append(f"[{s['index']}] {s['title']} — {s['url']}")

    return f"{summary}\n" + "\n".join(source_lines)


async def fetch_topic_news(topic: str = "tech") -> str:
    """Fetch real-time breaking news headlines and summaries for a topic (tech, linux, ai, science, security, world)."""
    articles = await fetch_news(topic=topic, limit=6)
    if not articles:
        return f"No recent headlines found for topic '{topic}'."

    lines = [f"JARVIS Real-Time News Feed [{topic.upper()}]:"]
    lines.append("=" * 65)
    for idx, a in enumerate(articles, start=1):
        lines.append(f"{idx}. {a['title']}")
        lines.append(f"   Published: {a['published']}")
        lines.append(f"   Summary:   {a['summary']}")
        lines.append(f"   Link:      {a['url']}\n")
    lines.append("=" * 65)

    return "\n".join(lines)


async def extract_web_article(url: str) -> str:
    """Fetch and extract sanitized readable article text from a web URL, stripping ads and HTML clutter."""
    res = await extract_article(url)
    if not res["success"]:
        return f"Failed to extract article from '{url}': {res['content']}"

    return (
        f"Article Title: {res['title']}\n"
        f"Source URL:    {res['url']}\n"
        f"Length:        {res['length']} characters\n\n"
        f"Content:\n{res['content']}"
    )
