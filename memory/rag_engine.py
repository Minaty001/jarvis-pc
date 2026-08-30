"""
RAG Engine — Vector Store for Semantic Search.
Uses ChromaDB for embedding-based retrieval.
"""

from typing import Any, Optional

from config.logger import get_logger

logger = get_logger("memory.rag")

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False
    logger.warning("chromadb not installed. RAG engine disabled.")


class RAGEngine:
    """ChromaDB-backed vector store for semantic retrieval."""

    def __init__(self):
        self._client = None
        self._collection = None
        self._init_chroma()

    def _init_chroma(self) -> None:
        if not HAS_CHROMA:
            return
        try:
            from config.settings import settings
            self._client = chromadb.Client(ChromaSettings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(settings.data_dir / "chromadb"),
                anonymized_telemetry=False,
            ))
            self._collection = self._client.get_or_create_collection(
                name="jarvis_memory",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB initialized. %d documents stored.", self._collection.count())
        except Exception as e:
            logger.error("ChromaDB init failed: %s", e)
            self._client = None

    def add(self, doc_id: str, text: str, metadata: Optional[dict] = None) -> None:
        if not self._collection:
            return
        try:
            self._collection.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata or {}],
            )
        except Exception as e:
            logger.error("RAG add failed: %s", e)

    def query(self, text: str, n_results: int = 5) -> list[dict[str, Any]]:
        if not self._collection:
            return []
        try:
            results = self._collection.query(
                query_texts=[text],
                n_results=n_results,
            )
            docs = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                meta = results.get("metadatas", [{}])[0][i] if results.get("metadatas") else {}
                dist = results.get("distances", [[]])[0][i] if results.get("distances") else 0
                docs.append({"id": results["ids"][0][i], "text": doc, "metadata": meta, "score": 1 - dist})
            return docs
        except Exception as e:
            logger.error("RAG query failed: %s", e)
            return []

    def delete(self, doc_id: str) -> None:
        if not self._collection:
            return
        try:
            self._collection.delete(ids=[doc_id])
        except Exception as e:
            logger.error("RAG delete failed: %s", e)

    @property
    def count(self) -> int:
        return self._collection.count() if self._collection else 0


rag_engine = RAGEngine()
