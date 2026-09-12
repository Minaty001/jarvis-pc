"""Unit tests for Visual Grounder UI element localization."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from jarvis.brain.vision.grounding import VisualGrounder
from jarvis.brain.vision.ocr import BoundingBox, OCRTextElement, ScreenOCREngine


@pytest.mark.asyncio
async def test_visual_grounder_ocr_fast_path(tmp_path):
    """Verify fast-path visual localization using exact OCR match."""
    dummy_img = tmp_path / "screen.png"
    dummy_img.write_bytes(b"image")

    mock_ocr = MagicMock(spec=ScreenOCREngine)
    mock_ocr.find_text.return_value = [
        OCRTextElement(text="Submit", bbox=BoundingBox(x=500, y=300, width=60, height=20), confidence=0.98)
    ]

    grounder = VisualGrounder(ocr_engine=mock_ocr)
    res = await grounder.locate_element("Submit", dummy_img)

    assert res["found"]
    assert res["x"] == 530
    assert res["y"] == 310
    assert res["method"] == "ocr"


@pytest.mark.asyncio
async def test_visual_grounder_vision_llm_fallback(tmp_path):
    """Verify fallback to Vision LLM coordinate grounding when OCR text not matched."""
    dummy_img = tmp_path / "screen.png"
    dummy_img.write_bytes(b"image")

    mock_ocr = MagicMock(spec=ScreenOCREngine)
    mock_ocr.find_text.return_value = []

    mock_llm = MagicMock()
    mock_llm.analyze_image = AsyncMock(return_value='{"found": true, "x": 850, "y": 420, "confidence": 0.88}')

    grounder = VisualGrounder(ocr_engine=mock_ocr, llm_client=mock_llm)
    res = await grounder.locate_element("blue refresh icon", dummy_img)

    assert res["found"]
    assert res["x"] == 850
    assert res["y"] == 420
    assert res["method"] == "vision_llm"
