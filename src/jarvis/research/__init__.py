"""Autonomous Web Research, Article Extraction & Real-Time News Intelligence Hub."""

from jarvis.research.engine import ResearchEngine, get_research_engine
from jarvis.research.extractor import extract_article
from jarvis.research.news import fetch_news
from jarvis.research.search import search_web, search_wikipedia

__all__ = [
    "ResearchEngine",
    "get_research_engine",
    "search_web",
    "search_wikipedia",
    "extract_article",
    "fetch_news",
]
