"""Unit tests for Screen OCR Engine and Bounding Box calculation."""

from unittest.mock import MagicMock, patch
import pytest
from jarvis.brain.vision.ocr import BoundingBox, OCRTextElement, ScreenOCREngine


def test_bounding_box_center_and_serialization():
    """Verify BoundingBox geometry and center calculations."""
    bbox = BoundingBox(x=100, y=200, width=50, height=40)
    assert bbox.center == (125, 220)
    d = bbox.to_dict()
    assert d["center_x"] == 125
    assert d["center_y"] == 220


def test_ocr_text_element_serialization():
    """Verify OCRTextElement dictionary formatting."""
    bbox = BoundingBox(x=10, y=20, width=30, height=15)
    elem = OCRTextElement(text="Deploy", bbox=bbox, confidence=0.92)
    d = elem.to_dict()
    assert d["text"] == "Deploy"
    assert d["confidence"] == 0.92
    assert d["bbox"]["x"] == 10


def test_screen_ocr_engine_tsv_parsing(tmp_path):
    """Verify parsing TSV output from tesseract."""
    engine = ScreenOCREngine()
    dummy_img = tmp_path / "test.png"
    dummy_img.write_bytes(b"dummy_png_bytes")

    fake_tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t120\t240\t60\t25\t95\tSettings\n"
        "5\t1\t1\t1\t1\t2\t300\t450\t80\t30\t88\tTerminal\n"
    )

    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = fake_tsv

    with patch("shutil.which", return_value="/usr/bin/tesseract"), \
         patch("subprocess.run", return_value=mock_res):

        elements = engine.extract_text_elements(dummy_img)
        assert len(elements) == 2
        assert elements[0].text == "Settings"
        assert elements[0].bbox.center == (150, 252)

        # Test search
        matches = engine.find_text(query="terminal", image_path=dummy_img)
        assert len(matches) == 1
        assert matches[0].text == "Terminal"
