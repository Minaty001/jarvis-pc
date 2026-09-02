import asyncio
import logging
from typing import Callable, Awaitable, Any

logger = logging.getLogger(__name__)


async def with_retry(
    fn: Callable[[], Awaitable[Any]],
    max_retries: int = 3,
    delay_seconds: float = 1.0,
) -> Any:
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            logger.warning("Attempt %d/%d failed: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                await asyncio.sleep(delay_seconds * (2 ** (attempt - 1)))
    raise last_exc  # type: ignore
