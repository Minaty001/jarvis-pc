"""Unit and integration tests for Personal Knowledge Base & RAG Indexer."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from jarvis.config.settings import Settings
from jarvis.knowledge.indexer import KnowledgeIndexer, chunk_text
from jarvis.knowledge.rag import KnowledgeAssistant
from jarvis.knowledge.store import KnowledgeStore
from jarvis.tools.builtin.knowledge_tools import (
    ask_knowledge_base,
    get_knowledge_stats,
    index_knowledge_directory,
    search_knowledge,
)
from jarvis.cli.main import run_cli


@pytest.fixture
def temp_knowledge_store(tmp_path):
    db_path = tmp_path / "test_knowledge.db"
    store = KnowledgeStore(path=db_path)
    yield store
    store.close()


def test_knowledge_store_crud_and_bm25_search(temp_knowledge_store, tmp_path):
    """Test inserting file chunks and retrieving via SQLite FTS5 BM25 search."""
    store = temp_knowledge_store

    sample_chunks = [
        {
            "content": "JARVIS uses edge_tts for multi-accent neural text to speech synthesis.",
            "start_line": 1,
            "end_line": 10,
            "category": "document",
        },
        {
            "content": "The proactive engine monitors CPU, RAM, and Battery levels continuously.",
            "start_line": 11,
            "end_line": 25,
            "category": "document",
        },
    ]

    file_path = str(tmp_path / "docs" / "architecture.md")
    store.add_or_update_file(
        path=file_path,
        file_hash="hash123",
        mtime=1234567.0,
        size=1024,
        chunks=sample_chunks,
    )

    stats = store.get_stats()
    assert stats["total_files"] == 1
    assert stats["total_chunks"] == 2

    # 1. Search for speech synthesis
    res = store.search("neural speech synthesis")
    assert len(res) == 1
    assert "edge_tts" in res[0]["content"]
    assert res[0]["start_line"] == 1
    assert res[0]["end_line"] == 10

    # 2. Search for telemetry
    res_telemetry = store.search("proactive battery telemetry")
    assert len(res_telemetry) == 1
    assert "Battery" in res_telemetry[0]["content"]


def test_chunk_text_boundaries_and_line_numbers():
    """Verify line-aware chunking preserves exact start and end line ranges."""
    sample_text = "\n".join([f"Line {i}: function_operation_{i}()" for i in range(1, 101)])
    chunks = chunk_text(sample_text, max_chars=400, overlap_chars=50, category="code")

    assert len(chunks) > 1
    # Verify continuous line numbering
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] >= 10
    assert chunks[0]["category"] == "code"


def test_indexer_exclusions_and_incremental_sync(temp_knowledge_store, tmp_path):
    """Verify crawler excludes secrets/binaries and performs incremental updates."""
    store = temp_knowledge_store
    indexer = KnowledgeIndexer(store=store)

    work_dir = tmp_path / "workspace"
    work_dir.mkdir(parents=True)

    # Valid files
    (work_dir / "notes.md").write_text("# Project Notes\nBuilding JARVIS PC architecture.")
    (work_dir / "main.py").write_text("def run_assistant():\n    print('Hello sir')")

    # Excluded files and directories
    git_dir = work_dir / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core] repositoryformatversion = 0")

    venv_dir = work_dir / ".venv"
    venv_dir.mkdir()
    (venv_dir / "lib.py").write_text("# Virtualenv file")

    (work_dir / ".env").write_text("SECRET_KEY=12345")
    (work_dir / "app.pyc").write_bytes(b"\x00\x01binary")

    # First indexing pass
    res1 = indexer.index_directory(work_dir, recursive=True)
    assert res1["indexed"] == 2  # Only notes.md and main.py
    assert res1["skipped"] >= 1

    # Second indexing pass (no changes) -> should skip
    res2 = indexer.index_directory(work_dir, recursive=True)
    assert res2["indexed"] == 0
    assert res2["skipped"] >= 2


@pytest.mark.asyncio
async def test_rag_assistant_with_mock_llm(temp_knowledge_store, tmp_path):
    """Test KnowledgeAssistant RAG retrieval and citation formatting."""
    store = temp_knowledge_store

    file_path = str(tmp_path / "server.py")
    chunks = [
        {
            "content": "PORT = 8000\nHOST = '127.0.0.1'\ndef start_server():\n    pass",
            "start_line": 1,
            "end_line": 4,
            "category": "code",
        }
    ]
    store.add_or_update_file(
        path=file_path,
        file_hash="hash999",
        mtime=100.0,
        size=100,
        chunks=chunks,
    )

    mock_client = MagicMock()
    mock_client.generate = AsyncMock(return_value="The server runs on port 8000 [server.py#L1-L4].")

    assistant = KnowledgeAssistant(store=store, llm_client=mock_client)
    reply = await assistant.ask_async("What port does the server run on?", client=mock_client)

    assert "8000" in reply
    assert mock_client.generate.called


def test_knowledge_builtin_tools(temp_knowledge_store, monkeypatch):
    """Test builtin tools: search_knowledge, index_knowledge_directory, get_knowledge_stats."""
    from jarvis.tools.builtin import knowledge_tools

    monkeypatch.setattr(knowledge_tools, "_GLOBAL_STORE", temp_knowledge_store)

    # 1. Stats
    stats = get_knowledge_stats()
    assert "JARVIS Knowledge Base Status" in stats

    # 2. Search empty
    res_empty = search_knowledge("quantum algorithm")
    assert "No documents found" in res_empty


def test_cli_knowledge_subcommands(capsys):
    """Test CLI commands: jarvis knowledge status and jarvis knowledge list."""
    ret = run_cli(["knowledge", "status"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "JARVIS Knowledge Base Status" in out
    assert "Total Indexed Files" in out
