"""Tests for the SchedulerManager component."""

import asyncio
from datetime import timedelta

import pytest

from jarvis.scheduler import SchedulerManager


@pytest.mark.asyncio
async def test_start_stop_lifecycle():
    mgr = SchedulerManager()
    await mgr.start()
    assert mgr.jobs == []
    await mgr.stop()
    assert mgr.jobs == []


@pytest.mark.asyncio
async def test_every_job_fires():
    mgr = SchedulerManager()
    await mgr.start()
    fired: list[int] = []

    async def tick():
        fired.append(1)

    mgr.every(timedelta(milliseconds=50), tick)
    await asyncio.sleep(0.25)
    await mgr.stop()
    assert len(fired) >= 2


@pytest.mark.asyncio
async def test_start_is_idempotent():
    mgr = SchedulerManager()
    await mgr.start()
    await mgr.start()  # no-op, no exception
    await mgr.stop()