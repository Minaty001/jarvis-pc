"""
Media Play — Direct video/song playback, volume control, and YouTube/Spotify integration.
"""

import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from typing import Any, Optional

from config.logger import get_logger

logger = get_logger("tools.media_control")


def _fetch_youtube_first_video_id(query: str) -> Optional[str]:
    """Extract first matching YouTube video ID via fast scraping or yt-dlp."""
    try:
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        html = urllib.request.urlopen(req, timeout=3.5).read().decode("utf-8", errors="ignore")
        video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
        if video_ids:
            return video_ids[0]
    except Exception as e:
        logger.debug("Fast YouTube scrape error: %s", e)

    # Fallback to yt-dlp if available
    if shutil.which("yt-dlp"):
        try:
            res = subprocess.run(
                ["yt-dlp", f"ytsearch1:{query}", "--get-id"],
                capture_output=True, text=True, timeout=4,
            )
            vid = res.stdout.strip()
            if vid and len(vid) == 11:
                return vid
        except Exception:
            pass

    return None


def play_on_youtube(query: str) -> dict[str, Any]:
    """Directly play a YouTube video or song in the browser."""
    if not query or not query.strip():
        url = "https://youtube.com"
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "result": "Opened YouTube"}

    clean_query = query.strip()
    video_id = _fetch_youtube_first_video_id(clean_query)

    if video_id:
        url = f"https://www.youtube.com/watch?v={video_id}"
        msg = f"Playing '{clean_query}' on YouTube"
    else:
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(clean_query)}"
        msg = f"Opened YouTube search for '{clean_query}'"

    try:
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info(msg)
        return {"success": True, "result": msg}
    except Exception as e:
        msg = f"Could not open YouTube: {e}"
        logger.error(msg)
        return {"success": False, "error": str(e), "result": msg}


def media_play(query: str = "") -> dict[str, Any]:
    """Play media directly or search for music/video."""
    if query:
        clean_query = query.strip()
        # Use local players ONLY if query is an actual local file or audio/video URL
        if os.path.exists(clean_query) or clean_query.startswith(("http://", "https://", "file://")):
            for player in ("vlc", "mpv", "rhythmbox", "audacious", "clementine"):
                if shutil.which(player):
                    try:
                        subprocess.Popen(
                            [player, clean_query],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        return {"success": True, "result": f"Playing '{clean_query}' in {player}"}
                    except Exception:
                        continue
        # For general song/video search queries ("play kuku song"), default to YouTube Direct Play
        return play_on_youtube(clean_query)

    # Toggle playback via playerctl
    try:
        subprocess.run(["playerctl", "play-pause"], check=True, capture_output=True)
        return {"success": True, "result": "Toggled media playback"}
    except Exception:
        pass
    try:
        subprocess.run(["dbus-send", "--print-reply", "--dest=org.mpris.MediaPlayer2.spotify",
                        "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player.PlayPause"],
                       capture_output=True)
        return {"success": True, "result": "Toggled Spotify playback"}
    except Exception:
        pass
    return {"success": False, "result": "No media player found"}


def media_pause() -> dict[str, Any]:
    """Pause media playback."""
    try:
        subprocess.run(["playerctl", "pause"], check=True, capture_output=True)
        return {"success": True, "result": "Media paused"}
    except Exception:
        return {"success": False, "result": "Could not pause media"}


def set_volume(level: str) -> dict[str, Any]:
    """Set system volume (0-100 or 'up'/'down'/'mute')."""
    level = str(level).strip().lower()
    try:
        if level in ("up", "higher"):
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"], check=True)
            return {"success": True, "result": "Volume increased"}
        elif level in ("down", "lower"):
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"], check=True)
            return {"success": True, "result": "Volume decreased"}
        elif level in ("mute", "0", "off"):
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=True)
            return {"success": True, "result": "Volume muted/unmuted"}
        else:
            pct = int(level.replace("%", "").strip())
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"], check=True)
            return {"success": True, "result": f"Volume set to {pct}%"}
    except Exception as e:
        # Fallback: amixer
        try:
            pct = int(level.replace("%", "").strip())
            subprocess.run(["amixer", "set", "Master", f"{pct}%"], capture_output=True)
            return {"success": True, "result": f"Volume set to {pct}%"}
        except Exception:
            pass
        return {"success": False, "error": str(e), "result": f"Could not set volume to {level}"}


def play_on_spotify(query: str) -> dict[str, Any]:
    """Search and play a song on Spotify."""
    if not query:
        subprocess.Popen(["xdg-open", "https://open.spotify.com"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "result": "Opened Spotify"}
    if shutil.which("spotify"):
        try:
            subprocess.Popen(["spotify", f"--uri=spotify:search:{urllib.parse.quote_plus(query)}"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"success": True, "result": f"Playing '{query}' on Spotify"}
        except Exception:
            pass
    url = f"https://open.spotify.com/search/{urllib.parse.quote_plus(query)}"
    subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"success": True, "result": f"Opened Spotify search for '{query}'"}
