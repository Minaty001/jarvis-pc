"""Visual UI Grounding and Element Coordinate Resolver for JARVIS PC."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from jarvis.brain.client import LLMClient
from jarvis.brain.vision.ocr import ScreenOCREngine

logger = logging.getLogger(__name__)


class VisualGrounder:
    """Resolves natural language UI descriptions to exact interactive screen coordinates."""

    def __init__(
        self,
        ocr_engine: Optional[ScreenOCREngine] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        self.ocr = ocr_engine or ScreenOCREngine()
        self.llm = llm_client or LLMClient.from_settings()

    async def locate_element(
        self,
        description: str,
        image_path: str | Path,
    ) -> Dict[str, Any]:
        """Locate target UI element on screen and return center pixel coordinates."""
        p = Path(image_path).resolve()
        if not p.is_file():
            return {
                "found": False,
                "description": description,
                "error": f"Screenshot file '{image_path}' does not exist.",
            }

        # 1. OCR Keyword Fast Path
        ocr_matches = self.ocr.find_text(query=description, image_path=p)
        if ocr_matches:
            best_match = ocr_matches[0]
            cx, cy = best_match.bbox.center
            logger.info("VisualGrounder: Found element via OCR '%s' at (%d, %d)", best_match.text, cx, cy)
            return {
                "found": True,
                "description": description,
                "matched_text": best_match.text,
                "x": cx,
                "y": cy,
                "width": best_match.bbox.width,
                "height": best_match.bbox.height,
                "method": "ocr",
                "confidence": best_match.confidence,
            }

        # 2. Multi-Modal Vision Model Grounding
        prompt = (
            f"Locate the UI element described as: '{description}'. "
            "Return JSON only with exact pixel coordinates in the format: "
            '{"x": integer, "y": integer, "found": true/false, "confidence": float}'
        )

        try:
            raw_reply = await self.llm.analyze_image(p, prompt=prompt)
            match = re.search(r"\{[^{}]*\}", raw_reply)
            if match:
                parsed = json.loads(match.group(0))
                if parsed.get("found", True) and "x" in parsed and "y" in parsed:
                    return {
                        "found": True,
                        "description": description,
                        "x": int(parsed["x"]),
                        "y": int(parsed["y"]),
                        "method": "vision_llm",
                        "confidence": float(parsed.get("confidence", 0.9)),
                    }
        except Exception as exc:
            logger.debug("Vision LLM grounding failed: %s", exc)

        return {
            "found": False,
            "description": description,
            "error": f"Could not locate element '{description}' on screen.",
        }
