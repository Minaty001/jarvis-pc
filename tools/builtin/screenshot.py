"""Screenshot — Capture screen."""

import subprocess
from pathlib import Path
from typing import Any

from config.logger import get_logger
from config.settings import settings

logger = get_logger("tools.screenshot")


def take_screenshot() -> dict[str, Any]:
    """Take a screenshot using scrot or import."""
    output = settings.data_dir / "screenshot.png"
    try:
        result = subprocess.run(
            ["scrot", str(output)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return {"success": True, "result": f"Screenshot saved to {output}"}
        # Fallback to import (ImageMagick)
        result = subprocess.run(
            ["import", "-window", "root", str(output)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return {"success": True, "result": f"Screenshot saved to {output}"}
        return {"success": False, "result": "Screenshot tool not found (install scrot or imagemagick)"}
    except Exception as e:
        return {"success": False, "result": f"Screenshot failed: {e}"}
