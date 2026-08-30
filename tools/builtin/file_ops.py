"""File Operations — List, create, delete files."""

import os
import shutil
from pathlib import Path
from typing import Any

from config.logger import get_logger

logger = get_logger("tools.file_ops")


def list_files(path: str = ".") -> dict[str, Any]:
    """List files in directory."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return {"success": False, "result": f"Path not found: {path}"}
    if not p.is_dir():
        return {"success": False, "result": f"Not a directory: {path}"}

    items = []
    for item in sorted(p.iterdir()):
        prefix = "📁" if item.is_dir() else "📄"
        size = item.stat().st_size if item.is_file() else 0
        items.append(f"{prefix} {item.name} ({_format_size(size)})")

    return {"success": True, "result": f"Files in {p}:\n" + "\n".join(items[:30])}


def create_file(path: str, content: str = "") -> dict[str, Any]:
    """Create a file with optional content."""
    p = Path(path).expanduser().resolve()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        msg = f"Created file: {p}"
        logger.info(msg)
        return {"success": True, "result": msg}
    except Exception as e:
        return {"success": False, "result": f"Failed to create {path}: {e}"}


def delete_file(path: str) -> dict[str, Any]:
    """Delete a file."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return {"success": False, "result": f"File not found: {path}"}
    try:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        msg = f"Deleted: {p}"
        logger.info(msg)
        return {"success": True, "result": msg}
    except Exception as e:
        return {"success": False, "result": f"Failed to delete {path}: {e}"}


def _format_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.0f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
