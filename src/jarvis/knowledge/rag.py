"""Retrieval-Augmented Generation (RAG) assistant for local documents and codebases."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.brain.client import LLMClient
from jarvis.config.settings import Settings, get_settings
from jarvis.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)

RAG_SYSTEM_PROMPT = """You are JARVIS, an intelligent AI personal assistant and engineering copilot.
Answer the user's question accurately using ONLY the provided knowledge base snippets.
When quoting facts, code, or configuration, cite the source file and line numbers using bracket notation (e.g. `[src/main.py#L20-L45]`).
If the provided context does not contain the answer, state clearly that the answer is not present in the indexed local documents.
"""


class KnowledgeAssistant:
    """RAG assistant for querying indexed documents and codebases."""

    def __init__(
        self,
        store: Optional[KnowledgeStore] = None,
        llm_client: Optional[LLMClient] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.store = store or KnowledgeStore(path=self.settings.knowledge_db_path)
        self.client = llm_client

    def retrieve(
        self,
        query: str,
        limit: int = 5,
        file_pattern: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant document/code chunks with BM25 ranking."""
        return self.store.search(query=query, limit=limit, file_pattern=file_pattern)

    def format_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks into a prompt context with line citations."""
        if not chunks:
            return "(No relevant documents found in knowledge base)"

        formatted = []
        for i, c in enumerate(chunks, start=1):
            path = c.get("path", "unknown")
            # Convert to relative path if within home or current directory for readability
            try:
                rel_path = str(Path(path).relative_to(Path.home()))
                display_path = f"~/{rel_path}"
            except ValueError:
                display_path = path

            start_l = c.get("start_line", 1)
            end_l = c.get("end_line", 1)
            citation = f"[{display_path}#L{start_l}-L{end_l}]"
            content = c.get("content", "").strip()

            formatted.append(f"--- Snippet #{i} {citation} ---\n{content}")

        return "\n\n".join(formatted)

    async def ask_async(
        self,
        question: str,
        limit: int = 4,
        file_pattern: Optional[str] = None,
        client: Optional[LLMClient] = None,
    ) -> str:
        """Query knowledge base and synthesize answer using LLM."""
        chunks = self.retrieve(question, limit=limit, file_pattern=file_pattern)
        if not chunks:
            return f"I searched the local knowledge base, but found no relevant documents matching '{question}'."

        context = self.format_context(chunks)
        target_client = client or self.client

        if target_client:
            user_prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer with file citations:"
            try:
                return await target_client.generate(
                    prompt=user_prompt,
                    system_prompt=RAG_SYSTEM_PROMPT,
                    temperature=0.2,
                )
            except Exception as exc:
                logger.warning("LLM generation failed for RAG query: %s; falling back to direct context snippet summary", exc)

        # Fallback summary with citations
        lines = [f"Found {len(chunks)} relevant excerpt(s) in local knowledge base:"]
        for c in chunks:
            path = c.get("path", "")
            try:
                display_path = f"~/{Path(path).relative_to(Path.home())}"
            except ValueError:
                display_path = path
            lines.append(f"\n• Source: {display_path} (Lines {c['start_line']}-{c['end_line']})")
            snippet = "\n  ".join(c["content"].strip().splitlines()[:6])
            lines.append(f"  {snippet}")
        return "\n".join(lines)

    def ask(
        self,
        question: str,
        limit: int = 4,
        file_pattern: Optional[str] = None,
        client: Optional[LLMClient] = None,
    ) -> str:
        """Synchronous wrapper for ask_async."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run,
                    self.ask_async(question, limit=limit, file_pattern=file_pattern, client=client),
                ).result()
        else:
            return asyncio.run(
                self.ask_async(question, limit=limit, file_pattern=file_pattern, client=client)
            )
