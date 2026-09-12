"""Unit tests for ScreenWatcherService and visual state monitoring."""

from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import pytest
from jarvis.brain.vision.watcher import ScreenWatcherService, compute_file_hash


def test_compute_file_hash(tmp_path):
    f1 = tmp_path / "img1.png"
    f1.write_bytes(b"content_a")
    h1 = compute_file_hash(f1)
    assert len(h1) == 64

    f2 = tmp_path / "img2.png"
    f2.write_bytes(b"content_b")
    h2 = compute_file_hash(f2)
    assert h1 != h2


@pytest.mark.asyncio
async def test_screen_watcher_detects_event(tmp_path):
    """Verify ScreenWatcher detects event and returns confirmation."""
    mock_llm = MagicMock()
    mock_llm.analyze_image = AsyncMock(return_value="YES — Build completed successfully with exit code 0.")

    watcher = ScreenWatcherService(llm_client=mock_llm)

    with patch("jarvis.brain.vision.watcher.take_screenshot", new_callable=AsyncMock, return_value=f"Screenshot saved to {tmp_path}/shot.png"):
        (tmp_path / "shot.png").write_bytes(b"image_data")
        res = await watcher.watch_for_event("build completed", timeout_seconds=2.0, poll_interval=0.1)
        assert res["triggered"]
        assert "Build completed" in res["observation"]
