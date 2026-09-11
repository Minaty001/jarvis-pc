"""Builtin agent tools for querying and managing local personal knowledge base."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from jarvis.knowledge.indexer import KnowledgeIndexer
from jarvis.knowledge.rag import KnowledgeAssistant
from jarvis.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)

_GLOBAL_STORE: Optional[KnowledgeStore] = None


def _get_store() -> KnowledgeStore:
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        _GLOBAL_STORE = KnowledgeStore()
    return _GLOBAL_STORE


def search_knowledge(
    query: str,
    limit: int = 5,
    file_pattern: Optional[str] = None,
) -> str:
    """Search the local knowledge base (notes, documents, codebases) using BM25 semantic matching."""
    store = _get_store()
    results = store.search(query=query, limit=limit, file_pattern=file_pattern)
    if not results:
        return f"No documents found matching '{query}' in the knowledge base."

    lines = [f"Found {len(results)} matching snippet(s):"]
    for i, r in enumerate(results, start=1):
        try:
            display_path = f"~/{Path(r['path']).relative_to(Path.home())}"
        except ValueError:
            display_path = r["path"]
        lines.append(f"\n[{i}] {display_path} (Lines {r['start_line']}-{r['end_line']}) [BM25: {r['score']}]")
        lines.append(f"    {r['content'].strip()[:250]}...")
    return "\n".join(lines)


def index_knowledge_directory(path: str, recursive: bool = True) -> str:
    """Scan and index all documents and code in a local directory into the knowledge base."""
    store = _get_store()
    indexer = KnowledgeIndexer(store=store)
    res = indexer.index_directory(path, recursive=recursive)
    return (
        f"Indexed directory '{res['directory']}': "
        f"{res['indexed']} file(s) indexed, {res['skipped']} skipped, {res['errors']} error(s)."
    )


def ask_knowledge_base(question: str) -> str:
    """Ask a question to be answered using the local indexed files with source citations."""
    store = _get_store()
    assistant = KnowledgeAssistant(store=store)
    return assistant.ask(question)


def get_knowledge_stats() -> str:
    """Get statistics about indexed documents, chunks, and storage in the knowledge base."""
    store = _get_store()
    stats = store.get_stats()
    mb = stats["total_bytes"] / (1024 * 1024)
    return (
        f"JARVIS Knowledge Base Status:\n"
        f"• Total Indexed Files:  {stats['total_files']}\n"
        f"• Total Text Chunks:    {stats['total_chunks']}\n"
        f"• Total Data Size:      {mb:.2f} MB\n"
        f"• Database Path:        {stats['db_path']}"
    )
