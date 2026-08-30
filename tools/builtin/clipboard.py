"""Clipboard Operations."""

import subprocess
from typing import Any

from config.logger import get_logger

logger = get_logger("tools.clipboard")


def clipboard_copy(text: str) -> dict[str, Any]:
    """Copy text to clipboard using xclip."""
    try:
        proc = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
        proc.communicate(text.encode())
        return {"success": True, "result": "Copied to clipboard"}
    except Exception as e:
        return {"success": False, "result": f"Copy failed: {e}"}


def clipboard_paste() -> dict[str, Any]:
    """Get clipboard content."""
    try:
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True, text=True, timeout=5,
        )
        content = result.stdout.strip()
        if content:
            return {"success": True, "result": f"Clipboard: {content[:500]}"}
        return {"success": True, "result": "Clipboard is empty"}
    except Exception as e:
        return {"success": False, "result": f"Paste failed: {e}"}
