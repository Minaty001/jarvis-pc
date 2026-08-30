"""
Retry Manager — Handles retries with exponential backoff.
"""

import asyncio
import time
from typing import Any, Callable, Optional

from config.logger import get_logger

logger = get_logger("execution.retry")


class RetryManager:
    """Manages retry logic with exponential backoff."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        max_retries: Optional[int] = None,
        **kwargs,
    ) -> dict:
        """Execute a function with retry logic."""
        retries = max_retries if max_retries is not None else self.max_retries
        last_error = None

        for attempt in range(retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                if isinstance(result, dict) and result.get("success", False):
                    return result

                # Handle non-dict results gracefully
                if not isinstance(result, dict):
                    last_error = f"Non-dict result: {type(result).__name__}"
                else:
                    last_error = result.get("error", "Unknown error")
                logger.warning("Attempt %d failed: %s", attempt + 1, last_error)

            except Exception as e:
                last_error = str(e)
                logger.warning("Attempt %d exception: %s", attempt + 1, last_error)

            if attempt < retries:
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logger.info("Retrying in %.1fs (attempt %d/%d)", delay, attempt + 2, retries + 1)
                await asyncio.sleep(delay)

        return {
            "success": False,
            "error": f"Failed after {retries + 1} attempts: {last_error}",
            "attempts": retries + 1,
        }

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number."""
        return min(self.base_delay * (2 ** attempt), self.max_delay)


retry_manager = RetryManager()
