"""Autonomous Multi-Source Web Research & Synthesis Engine for JARVIS PC."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from jarvis.research.extractor import extract_article
from jarvis.research.search import search_web

logger = logging.getLogger(__name__)


class ResearchEngine:
    """Orchestrates multi-source search, deep web scraping, and factual synthesis."""

    def __init__(self, llm_client: Any = None) -> None:
        self.llm_client = llm_client

    async def research_topic(
        self,
        query: str,
        client: Optional[Any] = None,
        max_sources: int = 4,
    ) -> Dict[str, Any]:
        """Perform autonomous deep web investigation and synthesize findings with citations."""
        clean_query = query.strip()
        active_client = client or self.llm_client

        # 1. Search top sources
        search_results = await search_web(clean_query, limit=max_sources)
        if not search_results:
            return {
                "query": clean_query,
                "summary": f"No web sources or articles found for query '{clean_query}'.",
                "sources": [],
                "extracted_count": 0,
            }

        # 2. Extract content from sources concurrently
        fetch_tasks = [extract_article(r["url"], max_chars=3000) for r in search_results]
        extracted_articles = await asyncio.gather(*fetch_tasks)

        sources_data: List[Dict[str, Any]] = []
        context_blocks: List[str] = []

        for idx, (sr, art) in enumerate(zip(search_results, extracted_articles), start=1):
            title = art.get("title") or sr.get("title") or "Source"
            url = sr["url"]
            content = art.get("content") if art.get("success") else sr.get("snippet", "")

            sources_data.append({
                "index": idx,
                "title": title,
                "url": url,
                "snippet": sr.get("snippet", ""),
            })

            context_blocks.append(
                f"[Source {idx}] Title: {title}\nURL: {url}\nContent:\n{content[:2000]}"
            )

        combined_context = "\n\n" + ("=" * 50) + "\n\n".join(context_blocks)

        # 3. Synthesize via LLM if available
        if active_client:
            prompt = (
                f"You are JARVIS, conducting autonomous technical research on the following topic:\n"
                f"Research Query: \"{clean_query}\"\n\n"
                "Synthesize the provided web source extractions into an articulate, comprehensive executive dossier.\n"
                "Structure your response with:\n"
                "1. Executive Summary\n"
                "2. Key Findings & Technical Details\n"
                "3. Source References (referencing [Source 1], [Source 2], etc.)\n\n"
                f"Web Context:\n{combined_context}"
            )
            try:
                res = await active_client.complete(prompt)
                if res and res.strip():
                    return {
                        "query": clean_query,
                        "summary": res.strip(),
                        "sources": sources_data,
                        "extracted_count": len(sources_data),
                    }
            except Exception as exc:
                logger.debug("LLM research synthesis error (%s); falling back to heuristic", exc)

        # Heuristic synthesis fallback
        lines = [
            f"JARVIS Research Dossier: {clean_query}",
            "=" * 65,
            "\nKey Source Findings:\n",
        ]
        for s in sources_data:
            lines.append(f"[{s['index']}] {s['title']}")
            lines.append(f"    URL: {s['url']}")
            lines.append(f"    Summary: {s['snippet']}\n")

        lines.append("=" * 65)
        return {
            "query": clean_query,
            "summary": "\n".join(lines),
            "sources": sources_data,
            "extracted_count": len(sources_data),
        }


_RESEARCH_ENGINE: Optional[ResearchEngine] = None


def get_research_engine() -> ResearchEngine:
    """Get singleton ResearchEngine instance."""
    global _RESEARCH_ENGINE
    if _RESEARCH_ENGINE is None:
        _RESEARCH_ENGINE = ResearchEngine()
    return _RESEARCH_ENGINE
