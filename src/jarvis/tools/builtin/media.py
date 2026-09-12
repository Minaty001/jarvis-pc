"""
Media and Camera device utilities.
"""

import os
import re
from pathlib import Path
from urllib.parse import quote_plus

import httpx

from jarvis.system.process import ProcessResult, run_process


class CameraPermissionError(PermissionError):
    """Raised when access to a camera device is denied due to system permissions."""

    pass


def check_camera_permissions(device_path: str = "/dev/video0") -> bool:
    if not os.path.exists(device_path):
        return False

    if not os.access(device_path, os.R_OK | os.W_OK):
        raise CameraPermissionError(
            f"Permission denied accessing camera device '{device_path}'. "
            "Please ensure current user has access rights (e.g. member of 'video' group)."
        )

    return True


_YT_SEARCH_URL = "https://www.youtube.com/results?search_query={}"
_VIDEO_ID_RE = re.compile(r'"videoId"\s*:\s*"([A-Za-z0-9_-]{11})"')
_YT_WATCH = "https://www.youtube.com/watch?v={}"


async def play_song(query: str) -> str:
    """Resolve the top YouTube result for a query and open it in the browser."""
    search_url = _YT_SEARCH_URL.format(quote_plus(query.strip()))
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            search_url,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0"},
            follow_redirects=True,
        )
        resp.raise_for_status()

    match = _VIDEO_ID_RE.search(resp.text)
    if not match:
        return "Sorry, sir — no video found for that query."

    video_id = match.group(1)
    watch_url = _YT_WATCH.format(video_id)
    await run_process(["xdg-open", watch_url], timeout=10.0)
    return f"Opened video https://www.youtube.com/watch?v={video_id} (query: {query})"
