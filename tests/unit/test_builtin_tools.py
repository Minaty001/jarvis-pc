from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from jarvis.tools.builtin.applications import ApplicationError, open_application, open_url
from jarvis.tools.builtin.browser import browse_web
from jarvis.tools.builtin.media import play_song
from jarvis.tools.builtin.processes import find_processes


@pytest.mark.asyncio
async def test_play_song_opens_watch_url():
    html = '<script>var ytInitialData = {"videoId":"dQw4w9WgXcQ"}<script>'
    with patch("jarvis.tools.builtin.media.run_process", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = AsyncMock(returncode=0, stdout="", stderr="")
        with patch("jarvis.tools.builtin.media.httpx.AsyncClient") as mock_cls:
            resp = MagicMock()
            resp.text = html
            resp.raise_for_status = MagicMock()
            mock_cls.return_value.__aenter__.return_value.get.return_value = resp
            result = await play_song("headlights song")
    assert "watch?v=dQw4w9WgXcQ" in result
    mock_run.assert_called_once_with(["xdg-open", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"], timeout=10.0)


@pytest.mark.asyncio
async def test_play_song_no_result():
    with patch("jarvis.tools.builtin.media.httpx.AsyncClient") as mock_cls:
        resp = MagicMock()
        resp.text = "<html>no videos here</html>"
        resp.raise_for_status = MagicMock()
        mock_cls.return_value.__aenter__.return_value.get.return_value = resp
        result = await play_song("nonexistent")
    assert "no video found" in result


@pytest.mark.asyncio
async def test_open_url_uses_xdg_open():
    with patch("jarvis.tools.builtin.applications.run_process", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = AsyncMock(returncode=0, stdout="", stderr="")
        await open_url("https://youtube.com")
        mock_run.assert_called_once_with(["xdg-open", "https://youtube.com"], timeout=10.0)


@pytest.mark.asyncio
async def test_open_url_rejects_non_http_scheme():
    with pytest.raises(ApplicationError, match="unsupported URL scheme"):
        await open_url("file:///etc/passwd")


@pytest.mark.asyncio
async def test_open_application_disallowed():
    with pytest.raises(ApplicationError, match="not allowed"):
        await open_application("unauthorized_app_xyz")


@pytest.mark.asyncio
async def test_open_application_allowed():
    with patch("jarvis.tools.builtin.applications.run_process", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = AsyncMock(returncode=0, stdout="", stderr="")
        res = await open_application("firefox")
        mock_run.assert_called_once_with(["firefox"], timeout=10.0)


def test_find_processes():
    procs = find_processes("python3")
    assert isinstance(procs, list)


def test_find_processes_all():
    summary = find_processes()
    assert isinstance(summary, list) and len(summary) == 2
    assert "total" in summary[0]
    assert isinstance(summary[1]["sample"], list)


@pytest.mark.asyncio
async def test_browse_web_rejects_non_http_scheme():
    with pytest.raises(ValueError, match="unsupported URL scheme"):
        await browse_web("file:///etc/passwd")


@pytest.mark.asyncio
async def test_browse_web_returns_rendered_text():
    with (
        patch("jarvis.tools.builtin.browser.subprocess.Popen") as mock_popen,
        patch("jarvis.tools.builtin.browser._page_ws_url", new_callable=AsyncMock) as mock_ws,
        patch("jarvis.tools.builtin.browser._runtime_eval") as mock_eval,
        patch("jarvis.tools.builtin.browser.tempfile.mkdtemp", return_value="/tmp/fake-profile"),
        patch("jarvis.tools.builtin.browser.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_ws.return_value = "ws://127.0.0.1/debug"
        mock_eval.side_effect = ["Example Domain", "Example Domain\nFor use in illustrative examples"]
        result = await browse_web("https://example.com")
    assert "title: Example Domain" in result
    assert mock_popen.return_value.terminate.called
