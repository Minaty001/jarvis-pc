"""
Media Play — Play media, control system audio, and open YouTube/Spotify searches.
"""

import subprocess
import shutil
from typing import Any
from urllib.parse import quote_plus

from config.logger import get_logger

logger = get_logger("tools.media_control")


def media_play(query: str = "") -> dict[str, Any]:
    """Play media or search for music/video."""
    if query:
        # Try to play with local apps first
        for player in ("rhythmbox", "vlc", "mpv", "audacious", "clementine"):
            if shutil.which(player):
                try:
                    subprocess.Popen(
                        [player, query],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return {"success": True, "result": f"Playing '{query}' in {player}"}
                except Exception:
                    continue
        # Fallback: open YouTube search
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "result": f"Searching YouTube for '{query}'"}

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


def play_on_youtube(query: str) -> dict[str, Any]:
    """Search and open a YouTube video/song in the browser."""
    if not query:
        url = "https://youtube.com"
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "result": "Opened YouTube"}
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    try:
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        msg = f"Opened YouTube search for '{query}'"
        logger.info(msg)
        return {"success": True, "result": msg}
    except Exception as e:
        return {"success": False, "error": str(e), "result": f"Could not open YouTube: {e}"}


def play_on_spotify(query: str) -> dict[str, Any]:
    """Search and open a song on Spotify (browser fallback)."""
    if not query:
        subprocess.Popen(["xdg-open", "https://open.spotify.com"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "result": "Opened Spotify"}
    # Try Spotify URI first
    if shutil.which("spotify"):
        try:
            subprocess.Popen(["spotify", f"--uri=spotify:search:{quote_plus(query)}"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"success": True, "result": f"Searching Spotify for '{query}'"}
        except Exception:
            pass
    # Browser fallback
    url = f"https://open.spotify.com/search/{quote_plus(query)}"
    subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"success": True, "result": f"Opened Spotify search for '{query}'"}
