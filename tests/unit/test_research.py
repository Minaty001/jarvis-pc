"""Tests for Autonomous Web Research, Article Extraction & Real-Time News Intelligence."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from jarvis.cli.main import run_cli
from jarvis.research.engine import ResearchEngine
from jarvis.research.extractor import extract_article, sanitize_html
from jarvis.research.news import fetch_news
from jarvis.research.search import search_web, search_wikipedia
from jarvis.tools.builtin.research_tools import (
    deep_web_research,
    extract_web_article,
    fetch_topic_news,
)


# ==========================================
# Search & Wikipedia Tests
# ==========================================

@pytest.mark.asyncio
async def test_search_web_duckduckgo_mocked():
    mock_html = """
    <html>
        <body>
            <h2 class="result__title">
                <a class="result__snippet" href="/l/?kh=-1&uddg=https%3A%2F%2Fpython.org">Python Programming</a>
            </h2>
            <a class="result__snippet">Python is a high-level general-purpose language.</a>
        </body>
    </html>
    """
    with patch("httpx.AsyncClient") as mock_cls:
        resp = MagicMock()
        resp.status_code = 200
        resp.text = mock_html
        mock_cls.return_value.__aenter__.return_value.get.return_value = resp

        results = await search_web("Python programming language")
        assert len(results) >= 1
        assert "Python" in results[0]["title"]
        assert results[0]["url"] == "https://python.org"


@pytest.mark.asyncio
async def test_search_wikipedia_mocked():
    mock_json = [
        "quantum",
        ["Quantum computing", "Quantum mechanics"],
        ["Computing using quantum mechanics", "Physics branch"],
        ["https://en.wikipedia.org/wiki/Quantum_computing", "https://en.wikipedia.org/wiki/Quantum_mechanics"],
    ]
    with patch("httpx.AsyncClient") as mock_cls:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = mock_json
        mock_cls.return_value.__aenter__.return_value.get.return_value = resp

        results = await search_wikipedia("quantum")
        assert len(results) == 2
        assert "Quantum computing" in results[0]["title"]
        assert results[0]["url"] == "https://en.wikipedia.org/wiki/Quantum_computing"


# ==========================================
# Article Extractor & Sanitizer Tests
# ==========================================

def test_sanitize_html_strips_boilerplate():
    raw_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Linux Kernel 6.10 Released - Phoronix</title>
        <script>var tracker = 123;</script>
        <style>.ad { display: block; }</style>
    </head>
    <body>
        <header><nav><a href="/">Home</a><a href="/news">News</a></nav></header>
        <aside class="ads">Buy our sponsors product!</aside>
        <main>
            <h1>Linux Kernel 6.10 Released</h1>
            <p>Linus Torvalds announced the general release of Linux kernel 6.10 today with memory management improvements.</p>
            <p>This cycle includes performance optimizations for ARM64 and x86_64 architectures.</p>
        </main>
        <footer>Copyright 2026 Example Corp</footer>
    </body>
    </html>
    """
    parsed = sanitize_html(raw_html)
    assert parsed["title"] == "Linux Kernel 6.10 Released"
    assert "Linus Torvalds" in parsed["content"]
    assert "Buy our sponsors" not in parsed["content"]
    assert "var tracker" not in parsed["content"]
    assert "Copyright" not in parsed["content"]


@pytest.mark.asyncio
async def test_extract_article_success():
    with patch("httpx.AsyncClient") as mock_cls:
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "<html><head><title>Test Article</title></head><body><p>This is a complete long-form test article about artificial intelligence.</p></body></html>"
        mock_cls.return_value.__aenter__.return_value.get.return_value = resp

        res = await extract_article("https://example.com/article")
        assert res["success"] is True
        assert res["title"] == "Test Article"
        assert "artificial intelligence" in res["content"]


# ==========================================
# News Aggregator Tests
# ==========================================

@pytest.mark.asyncio
async def test_fetch_news_rss_parsing():
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Tech News</title>
            <item>
                <title>Rust 1.85 Released</title>
                <link>https://blog.rust-lang.org/2026/02/rust-1.85.html</link>
                <description>The Rust team is happy to announce a new version.</description>
                <pubDate>Thu, 15 Sep 2026 10:00:00 GMT</pubDate>
            </item>
        </channel>
    </rss>
    """
    with patch("httpx.AsyncClient") as mock_cls:
        resp = MagicMock()
        resp.status_code = 200
        resp.text = rss_xml
        mock_cls.return_value.__aenter__.return_value.get.return_value = resp

        articles = await fetch_news(topic="tech", limit=2)
        assert len(articles) >= 1
        assert articles[0]["title"] == "Rust 1.85 Released"
        assert "rust-lang.org" in articles[0]["url"]


# ==========================================
# Research Engine & Tools Tests
# ==========================================

@pytest.mark.asyncio
async def test_research_engine_orchestration():
    mock_search = [
        {"title": "eBPF Overview", "url": "https://ebpf.io", "snippet": "eBPF is a revolutionary technology."},
    ]
    mock_article = {
        "success": True,
        "title": "eBPF Overview",
        "url": "https://ebpf.io",
        "content": "eBPF allows running sandboxed programs in the Linux kernel without changing kernel source code.",
        "length": 100,
    }

    with patch("jarvis.research.engine.search_web", new_callable=AsyncMock, return_value=mock_search), \
         patch("jarvis.research.engine.extract_article", new_callable=AsyncMock, return_value=mock_article):

        engine = ResearchEngine()
        result = await engine.research_topic("Linux eBPF")

        assert result["query"] == "Linux eBPF"
        assert len(result["sources"]) == 1
        assert "eBPF" in result["summary"]
        assert result["sources"][0]["url"] == "https://ebpf.io"


@pytest.mark.asyncio
async def test_builtin_research_tools():
    mock_res = {
        "query": "AI Agents",
        "summary": "AI agents perceive and act autonomously in environments.",
        "sources": [{"index": 1, "title": "Agents Guide", "url": "https://example.com/agents"}],
    }
    with patch("jarvis.research.engine.ResearchEngine.research_topic", new_callable=AsyncMock, return_value=mock_res):
        out = await deep_web_research("AI Agents")
        assert "AI agents perceive" in out
        assert "https://example.com/agents" in out


# ==========================================
# CLI Execution Tests
# ==========================================

def test_cli_news_and_research_subcommands(capsys):
    mock_articles = [
        {"title": "New Linux Patch", "url": "https://kernel.org", "summary": "Performance patch merged.", "published": "Today"},
    ]
    with patch("jarvis.research.news.fetch_news", new_callable=AsyncMock, return_value=mock_articles):
        ret1 = run_cli(["news", "linux"])
        assert ret1 == 0
        captured = capsys.readouterr()
        assert "LINUX" in captured.out
        assert "New Linux Patch" in captured.out

    mock_article = {
        "success": True,
        "title": "Sample Article",
        "url": "https://example.com/art",
        "content": "Full extracted article content without ads.",
        "length": 45,
    }
    with patch("jarvis.research.extractor.extract_article", new_callable=AsyncMock, return_value=mock_article):
        ret2 = run_cli(["article", "https://example.com/art"])
        assert ret2 == 0
        captured = capsys.readouterr()
        assert "Sample Article" in captured.out
        assert "Full extracted article content" in captured.out
