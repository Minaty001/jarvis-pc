import asyncio
import pytest
from jarvis.app.application import Application


@pytest.mark.asyncio
async def test_application_run_until_stopped():
    """Application.run_until_stopped blocks until request_stop is called."""
    app = Application()
    task = asyncio.create_task(app.run_until_stopped())
    await asyncio.sleep(0.1)
    assert app.is_started
    app.request_stop()
    await task
    assert not app.is_started


@pytest.mark.asyncio
async def test_application_request_stop_before_start():
    """request_stop is safe to call before run_until_stopped."""
    app = Application()
    app.request_stop()  # Should not raise
