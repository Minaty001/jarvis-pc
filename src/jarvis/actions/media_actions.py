"""Media playback actions for Linux via MPRIS D-Bus & playerctl."""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Any, List

from .base import ActionResult, BaseAction

logger = logging.getLogger("jarvis.actions.media")


def get_active_mpris_players() -> List[str]:
    """Find all active MPRIS media players on the session bus."""
    if not shutil.which("dbus-send"):
        return []
    try:
        out = subprocess.check_output(
            [
                "dbus-send",
                "--session",
                "--dest=org.freedesktop.DBus",
                "--type=method_call",
                "--print-reply",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus.ListNames",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        players = []
        for line in out.splitlines():
            if "org.mpris.MediaPlayer2" in line and 'string "' in line:
                player_dest = line.split('string "', 1)[1].rstrip('"').strip()
                players.append(player_dest)
        return players
    except Exception as err:
        logger.debug("Failed to list MPRIS players: %s", err)
        return []


def send_mpris_command(method_name: str) -> bool:
    """Send playback control method to playerctl or active MPRIS players."""
    # 1. Try playerctl if available
    if shutil.which("playerctl"):
        cmd_map = {
            "PlayPause": "play-pause",
            "Next": "next",
            "Previous": "previous",
            "Stop": "stop",
        }
        arg = cmd_map.get(method_name, "play-pause")
        res = subprocess.run(["playerctl", arg], capture_output=True, check=False)
        if res.returncode == 0:
            return True

    # 2. D-Bus session bus fallback
    players = get_active_mpris_players()
    if not players:
        return False

    success = False
    for player in players:
        res = subprocess.run(
            [
                "dbus-send",
                "--session",
                "--type=method_call",
                f"--dest={player}",
                "/org/mpris/MediaPlayer2",
                f"org.mpris.MediaPlayer2.Player.{method_name}",
            ],
            capture_output=True,
            check=False,
        )
        if res.returncode == 0:
            success = True

    return success


class MediaPlayPauseAction(BaseAction):
    """Play, pause, or resume media playback."""
    name = "media_play_pause"
    description = "Toggle play/pause on music, video, or media playback."
    patterns = [
        r"\b(?:play|pause|resume)\s+(?:music|song|video|media|playback)?\b",
        r"\b(?:pause|resume|play)\b",
        r"\btoggle\s+(?:music|playback|media)\b",
    ]

    def execute(self, **kwargs: Any) -> ActionResult:
        success = send_mpris_command("PlayPause")
        if success:
            return ActionResult(success=True, message="Media playback toggled.")
        return ActionResult(success=False, message="No active media player found to control.")


class MediaNextAction(BaseAction):
    """Skip to next media track."""
    name = "media_next"
    description = "Skip to the next song or track."
    patterns = [
        r"\bnext\s+(?:song|track|music|video)\b",
        r"\bskip\s+(?:song|track|this)?\b",
    ]

    def execute(self, **kwargs: Any) -> ActionResult:
        success = send_mpris_command("Next")
        if success:
            return ActionResult(success=True, message="Skipped to next track.")
        return ActionResult(success=False, message="No active media player found to skip track.")


class MediaPreviousAction(BaseAction):
    """Return to previous media track."""
    name = "media_previous"
    description = "Go back to previous song or track."
    patterns = [
        r"\bprevious\s+(?:song|track|music|video)\b",
        r"\b(?:go\s+back|play\s+previous)\s+(?:song|track|music)?\b",
    ]

    def execute(self, **kwargs: Any) -> ActionResult:
        success = send_mpris_command("Previous")
        if success:
            return ActionResult(success=True, message="Returned to previous track.")
        return ActionResult(success=False, message="No active media player found to go back.")
