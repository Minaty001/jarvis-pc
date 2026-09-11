"""Tests for Autonomous Memory & Fact Extraction Pipeline."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from jarvis.brain.memory import MemoryStore
from jarvis.brain.memory_extractor import MemoryExtractor


def test_memory_extractor_heuristics():
    extractor = MemoryExtractor()

    # Name pattern
    f1 = extractor.extract_heuristics("Hi, my name is Bruce Wayne")
    assert len(f1) == 1
    assert f1[0]["key"] == "name"
    assert f1[0]["value"] == "Bruce Wayne"
    assert f1[0]["category"] == "personal"

    # Favorite pattern
    f2 = extractor.extract_heuristics("My favorite programming language is Python")
    assert len(f2) == 1
    assert f2[0]["key"] == "favorite_programming_language"
    assert f2[0]["value"] == "Python"
    assert f2[0]["category"] == "preference"

    # Preference pattern
    f3 = extractor.extract_heuristics("I prefer dark mode in all applications")
    assert len(f3) == 1
    assert f3[0]["key"] == "preference"
    assert "dark mode" in f3[0]["value"]

    # Explicit fact pattern
    f4 = extractor.extract_heuristics("Remember that server backup is at /mnt/data/backup")
    assert len(f4) == 1
    assert f4[0]["key"] == "explicit_fact"
    assert "/mnt/data/backup" in f4[0]["value"]

    # Location & Editor
    f5 = extractor.extract_heuristics("I live in London and my editor is Neovim")
    assert len(f5) == 2
    keys = [x["key"] for x in f5]
    assert "location" in keys
    assert "editor" in keys


@pytest.mark.asyncio
async def test_memory_extractor_llm_fallback():
    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.content = '[{"key": "pet_dog", "value": "Golden Retriever named Cooper", "category": "personal"}]'
    mock_client.chat = AsyncMock(return_value=mock_res)

    extractor = MemoryExtractor(llm_client=mock_client)
    facts = await extractor.extract_llm("I just adopted a lovely Golden Retriever named Cooper.", "How wonderful, sir.")
    
    assert len(facts) == 1
    assert facts[0]["key"] == "pet_dog"
    assert "Cooper" in facts[0]["value"]
    assert facts[0]["category"] == "personal"


@pytest.mark.asyncio
async def test_extractor_and_store_integration(tmp_path):
    db_file = tmp_path / "memory.db"
    store = MemoryStore(db_file)
    extractor = MemoryExtractor()

    stored = await extractor.extract_and_store(
        user_text="My name is Clark Kent and my project is DailyPlanet",
        assistant_reply="Understood, Mr. Kent.",
        memory=store,
    )

    assert len(stored) == 2
    profile = store.get_user_profile()
    assert profile["personal"]["name"] == "Clark Kent"
    assert profile["work"]["current_project"] == "DailyPlanet"
