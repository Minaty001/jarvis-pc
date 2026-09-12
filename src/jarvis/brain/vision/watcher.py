"""Continuous Visual Screen Watcher and State Change Detector for JARVIS PC."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from jarvis.brain.client import LLMClient
from jarvis.tools.builtin.screen import take_screenshot

logger = logging.getLogger(__name__)


def compute_file_hash(path: Path) -> str:
    """Compute fast SHA256 checksum of an image file."""
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class ScreenWatcherService:
    """Background visual observer that monitors screen state changes and verifies conditions."""

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm = llm_client or LLMClient.from_settings()

    async def watch_for_event(
        self,
        event_description: str,
        timeout_seconds: float = 30.0,
        poll_interval: float = 2.0,
    ) -> Dict[str, Any]:
        """Periodically capture screen and evaluate whether the target visual event has occurred."""
        start_time = time.time()
        deadline = start_time + timeout_seconds
        last_hash = ""

        logger.info("ScreenWatcher: Starting watch for event: '%s' (Timeout: %ds)", event_description, timeout_seconds)

        while time.time() < deadline:
            # Capture current frame
            try:
                res_str = await take_screenshot()
                # Extract file path from take_screenshot response
                match = re_match = None
                for word in res_str.split():
                    if word.endswith(".png") and Path(word).is_file():
                        screenshot_path = Path(word)
                        break
                else:
                    screenshot_path = Path.home() / "Pictures" / "jarvis_captures" / "screen_watch.png"

                cur_hash = compute_file_hash(screenshot_path)
                if cur_hash and cur_hash != last_hash:
                    last_hash = cur_hash
                    # Evaluate visual state with LLM
                    prompt = (
                        f"Look at this screenshot carefully. Has the following event occurred or is it visible on screen? "
                        f"Event: '{event_description}'. "
                        "Answer strictly YES or NO as the first word, followed by a 1-sentence observation."
                    )
                    ans = await self.llm.analyze_image(screenshot_path, prompt=prompt)
                    if ans.strip().upper().startswith("YES"):
                        elapsed = round(time.time() - start_time, 2)
                        logger.info("ScreenWatcher: Event '%s' verified after %.2fs", event_description, elapsed)
                        return {
                            "triggered": True,
                            "elapsed_seconds": elapsed,
                            "observation": ans.strip(),
                        }
            except Exception as exc:
                logger.debug("ScreenWatcher iteration error: %s", exc)

            await asyncio.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        logger.info("ScreenWatcher: Timed out waiting for '%s'", event_description)
        return {
            "triggered": False,
            "elapsed_seconds": elapsed,
            "observation": f"Timed out after {timeout_seconds}s without detecting event.",
        }
