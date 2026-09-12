"""Screen OCR Text Extraction and Spatial Bounding Box Locator for JARVIS PC."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess  # nosec B404
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    def to_dict(self) -> Dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "center_x": self.center[0],
            "center_y": self.center[1],
        }


@dataclass
class OCRTextElement:
    text: str
    bbox: BoundingBox
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "bbox": self.bbox.to_dict(),
            "confidence": self.confidence,
        }


class ScreenOCREngine:
    """Extracts on-screen text with spatial pixel bounding boxes."""

    def __init__(self, tesseract_bin: Optional[str] = None) -> None:
        self._custom_bin = tesseract_bin

    @property
    def _tesseract_bin(self) -> Optional[str]:
        return self._custom_bin or shutil.which("tesseract")

    @property
    def is_available(self) -> bool:
        return self._tesseract_bin is not None

    def extract_text_elements(self, image_path: str | Path) -> List[OCRTextElement]:
        """Perform OCR on an image file and return segmented text elements with bounding boxes."""
        p = Path(image_path).resolve()
        if not p.is_file():
            logger.warning("OCR image file not found: %s", image_path)
            return []

        if not self._tesseract_bin:
            logger.debug("Tesseract OCR binary not found on system PATH.")
            return []

        try:
            # Run tesseract with TSV output for bounding boxes
            res = subprocess.run(  # nosec B603
                [self._tesseract_bin, str(p), "stdout", "tsv"],
                capture_output=True,
                text=True,
                timeout=15.0,
                check=False,
            )
            if res.returncode != 0:
                logger.debug("Tesseract failed with code %d: %s", res.returncode, res.stderr)
                return []

            elements: List[OCRTextElement] = []
            lines = res.stdout.strip().splitlines()
            if len(lines) <= 1:
                return []

            header = lines[0].split("\t")
            for line in lines[1:]:
                parts = line.split("\t")
                if len(parts) != len(header):
                    continue

                row = dict(zip(header, parts))
                text = row.get("text", "").strip()
                if not text:
                    continue

                try:
                    left = int(row.get("left", 0))
                    top = int(row.get("top", 0))
                    width = int(row.get("width", 0))
                    height = int(row.get("height", 0))
                    conf = float(row.get("conf", 0)) / 100.0
                except (ValueError, TypeError):
                    continue

                if width > 0 and height > 0:
                    elements.append(
                        OCRTextElement(
                            text=text,
                            bbox=BoundingBox(x=left, y=top, width=width, height=height),
                            confidence=max(0.0, min(1.0, conf)),
                        )
                    )

            return elements
        except Exception as exc:
            logger.warning("OCR text extraction failed: %s", exc)
            return []

    def find_text(
        self,
        query: str,
        image_path: str | Path,
        match_case: bool = False,
    ) -> List[OCRTextElement]:
        """Find matching text elements on screen matching the query substring."""
        elements = self.extract_text_elements(image_path)
        clean_q = query if match_case else query.lower()

        matches = []
        for el in elements:
            cand = el.text if match_case else el.text.lower()
            if clean_q in cand or cand in clean_q:
                matches.append(el)
        return matches
