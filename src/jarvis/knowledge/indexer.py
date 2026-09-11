"""File crawler, chunker, and incremental indexer for JARVIS Knowledge Base."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from jarvis.config.settings import Settings, get_settings
from jarvis.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: Set[str] = {
    ".md", ".txt", ".rst",
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".rs", ".go", ".c", ".cpp", ".h", ".hpp",
    ".json", ".yaml", ".yml", ".toml",
    ".sh", ".bash", ".zsh",
    ".html", ".css", ".sql",
}

EXCLUDED_DIRS: Set[str] = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".env", "dist", "build", ".pytest_cache", ".mypy_cache",
    ".gemini", ".cache", ".local", ".vscode", ".idea",
}

EXCLUDED_FILES: Set[str] = {
    ".env", ".env.local", ".env.production",
    "id_rsa", "id_ed25519", "knowledge.db",
}


def compute_file_hash(content: bytes) -> str:
    """Compute SHA256 digest of file content."""
    return hashlib.sha256(content).hexdigest()


def detect_category(extension: str) -> str:
    """Categorize file by extension."""
    ext = extension.lower()
    if ext in {".md", ".txt", ".rst"}:
        return "document"
    elif ext in {".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".c", ".cpp", ".h", ".hpp", ".sh"}:
        return "code"
    elif ext in {".json", ".yaml", ".yml", ".toml"}:
        return "config"
    return "text"


def chunk_text(
    text: str,
    max_chars: int = 2000,
    overlap_chars: int = 300,
    category: str = "text",
) -> List[Dict[str, Any]]:
    """Line-aware text chunker that preserves accurate start and end line numbers."""
    lines = text.splitlines(keepends=True)
    if not lines:
        return []

    chunks: List[Dict[str, Any]] = []
    current_lines: List[str] = []
    current_len = 0
    start_line_idx = 1

    for i, line in enumerate(lines, start=1):
        current_lines.append(line)
        current_len += len(line)

        if current_len >= max_chars:
            chunk_content = "".join(current_lines)
            end_line_idx = start_line_idx + len(current_lines) - 1
            chunks.append(
                {
                    "content": chunk_content,
                    "start_line": start_line_idx,
                    "end_line": end_line_idx,
                    "category": category,
                }
            )

            # Slide window back for overlap
            overlap_len = 0
            overlap_lines: List[str] = []
            for rev_line in reversed(current_lines):
                if overlap_len + len(rev_line) > overlap_chars:
                    break
                overlap_lines.insert(0, rev_line)
                overlap_len += len(rev_line)

            start_line_idx = end_line_idx - len(overlap_lines) + 1
            current_lines = overlap_lines
            current_len = overlap_len

    if current_lines:
        chunk_content = "".join(current_lines)
        if chunk_content.strip():
            end_line_idx = start_line_idx + len(current_lines) - 1
            chunks.append(
                {
                    "content": chunk_content,
                    "start_line": start_line_idx,
                    "end_line": end_line_idx,
                    "category": category,
                }
            )

    return chunks


class KnowledgeIndexer:
    """Scans and indexes workspace files into the SQLite KnowledgeStore."""

    def __init__(
        self,
        store: Optional[KnowledgeStore] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.store = store or KnowledgeStore(path=self.settings.knowledge_db_path)

    def is_file_indexable(self, file_path: Path) -> bool:
        """Check if file matches supported extensions and is not ignored."""
        if file_path.name.startswith(".") or file_path.name in EXCLUDED_FILES:
            return False
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return False
        # Ensure none of parent directories are excluded
        for part in file_path.parts:
            if part in EXCLUDED_DIRS:
                return False
        return True

    def index_file(self, file_path: str | Path, force: bool = False) -> bool:
        """Index a single file if modified or forced."""
        path_obj = Path(file_path).resolve()
        if not path_obj.exists() or not path_obj.is_file():
            logger.debug("File does not exist: %s", path_obj)
            return False

        if not self.is_file_indexable(path_obj):
            return False

        try:
            stat = path_obj.stat()
            size = stat.st_size
            mtime = stat.st_mtime

            # Skip huge files (> 5MB)
            if size > 5 * 1024 * 1024 or size == 0:
                return False

            raw_bytes = path_obj.read_bytes()
            file_hash = compute_file_hash(raw_bytes)

            # Check existing file record
            if not force:
                info = self.store.get_file_info(str(path_obj))
                if info and info["file_hash"] == file_hash and info["mtime"] == mtime:
                    return False  # Already up to date

            # Decode text
            try:
                text_content = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text_content = raw_bytes.decode("latin-1", errors="ignore")

            category = detect_category(path_obj.suffix)
            chunks = chunk_text(
                text=text_content,
                max_chars=getattr(self.settings, "knowledge_chunk_size", 500) * 4,
                overlap_chars=getattr(self.settings, "knowledge_chunk_overlap", 100) * 4,
                category=category,
            )

            self.store.add_or_update_file(
                path=str(path_obj),
                file_hash=file_hash,
                mtime=mtime,
                size=size,
                chunks=chunks,
            )
            logger.info("Indexed '%s' (%d chunks)", path_obj.name, len(chunks))
            return True

        except Exception as exc:
            logger.warning("Error indexing file '%s': %s", path_obj, exc)
            return False

    def index_directory(
        self,
        directory_path: str | Path,
        recursive: bool = True,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Scan directory and index all eligible files."""
        dir_obj = Path(os.path.expanduser(str(directory_path))).resolve()
        if not dir_obj.exists() or not dir_obj.is_dir():
            logger.warning("Directory '%s' does not exist.", dir_obj)
            return {"scanned": 0, "indexed": 0, "skipped": 0, "errors": 0}

        scanned = 0
        indexed = 0
        skipped = 0
        errors = 0

        pattern = "**/*" if recursive else "*"
        for path_obj in dir_obj.glob(pattern):
            if not path_obj.is_file():
                continue

            # Check excluded parent directories
            if any(part in EXCLUDED_DIRS for part in path_obj.parts):
                continue

            scanned += 1
            if not self.is_file_indexable(path_obj):
                skipped += 1
                continue

            try:
                if self.index_file(path_obj, force=force):
                    indexed += 1
                else:
                    skipped += 1
            except Exception:
                errors += 1

        logger.info("Directory scan complete for '%s': scanned=%d, indexed=%d", dir_obj, scanned, indexed)
        return {
            "directory": str(dir_obj),
            "scanned": scanned,
            "indexed": indexed,
            "skipped": skipped,
            "errors": errors,
        }

    def sync_configured_dirs(self, force: bool = False) -> Dict[str, Any]:
        """Index all directories configured in Settings.knowledge_dirs."""
        raw_dirs = getattr(self.settings, "knowledge_dirs", "~/Documents,~/Notes")
        dirs = [d.strip() for d in raw_dirs.split(",") if d.strip()]

        total_scanned = 0
        total_indexed = 0
        results = []

        for d in dirs:
            expanded = Path(os.path.expanduser(d))
            if expanded.exists() and expanded.is_dir():
                res = self.index_directory(expanded, recursive=True, force=force)
                total_scanned += res["scanned"]
                total_indexed += res["indexed"]
                results.append(res)

        return {
            "total_scanned": total_scanned,
            "total_indexed": total_indexed,
            "details": results,
        }
