"""Utility actions: Time, Date, Desktop Notifications, Reminders."""

from __future__ import annotations

import datetime
import shutil
import subprocess
from typing import Any

from .base import ActionResult, BaseAction


class TimeAction(BaseAction):
    """Tells current local time."""
    name = "tell_time"
    description = "Tell the current local time."
    patterns = [
        r"\bwhat\s+time\s+is\s+it\b",
        r"\bwhat\s+is\s+the\s+time\b",
        r"\btell\s+(?:me\s+)?(?:the\s+)?time\b",
        r"\bcurrent\s+time\b",
        r"^(?:the\s+)?time$",
    ]

    def execute(self, **kwargs: Any) -> ActionResult:
        now = datetime.datetime.now()
        time_str = now.strftime("%I:%M %p").lstrip("0")
        return ActionResult(success=True, message=f"It is {time_str}.", data={"time": time_str})


class DateAction(BaseAction):
    """Tells current date and day."""
    name = "tell_date"
    description = "Tell today's date and day of the week."
    patterns = [
        r"\bwhat\s+date\s+is\s+it\b",
        r"\bwhat\s+is\s+the\s+date\b",
        r"\bwhat\s+day\s+is\s+it\b",
        r"\bwhat\s+day\s+is\s+(?:it\s+)?today\b",
        r"\bwhat\s+is\s+today's\s+date\b",
        r"\btell\s+(?:me\s+)?(?:the\s+)?date\b",
        r"\bcurrent\s+date\b",
        r"\btoday's\s+date\b",
        r"^(?:the\s+)?date$",
    ]

    def execute(self, **kwargs: Any) -> ActionResult:
        now = datetime.datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        return ActionResult(success=True, message=f"Today is {date_str}.", data={"date": date_str})


class NotifyAction(BaseAction):
    """Displays a desktop notification via notify-send."""
    name = "notify"
    description = "Display a system desktop notification popup."
    patterns = [
        r"(?:send\s+)?notification\s+(?P<text>.+)",
        r"notify\s+(?:me\s+)?(?P<text>.+)",
    ]

    def execute(self, text: str = "", **kwargs: Any) -> ActionResult:
        clean_text = text.strip()
        if not clean_text:
            return ActionResult(success=False, message="No notification text provided.")

        try:
            if shutil.which("notify-send"):
                subprocess.run(["notify-send", "JARVIS", clean_text], check=False)
                return ActionResult(success=True, message=f"Notification displayed: {clean_text}")
            return ActionResult(success=False, message="notify-send utility not available.")
        except Exception as err:
            return ActionResult(success=False, message=f"Failed to show notification: {err}")
