"""
Multimodal visual intelligence tools for analyzing photos, screenshots, and diagrams.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from jarvis.brain.client import LLMClient

logger = logging.getLogger(__name__)


async def analyze_image(
    image_path: str,
    prompt: str = "Describe what you see in this image in detail, noting any text, UI elements, or objects.",
    client: Optional[LLMClient] = None,
) -> str:
    """Analyze a photo, screenshot, or diagram using a vision model.

    Args:
        image_path: Absolute or relative path to an image file within the user's home directory.
        prompt: Question or instruction regarding the image content.
        client: Optional LLMClient instance (defaults to from_settings).

    Returns:
        Natural language description or answer based on the visual contents.

    Raises:
        ValueError: If image path is outside user's home directory.
        FileNotFoundError: If image file does not exist.
    """
    path = Path(image_path).expanduser().resolve()
    home = Path.home().resolve()
    try:
        path.relative_to(home)
    except ValueError:
        raise ValueError(f"Image path '{image_path}' must be inside your home directory ({home}).")

    if not path.exists():
        raise FileNotFoundError(f"Image file '{image_path}' does not exist.")

    if client is None:
        client = LLMClient.from_settings()

    return await client.analyze_image(path, prompt=prompt)
