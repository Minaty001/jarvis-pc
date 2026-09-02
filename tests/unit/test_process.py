import pytest
from jarvis.system.process import run_process, ProcessError


@pytest.mark.asyncio
async def test_run_process_success():
    res = await run_process(["echo", "hello"])
    assert res.returncode == 0
    assert "hello" in res.stdout


@pytest.mark.asyncio
async def test_run_process_timeout():
    with pytest.raises(ProcessError, match="timed out"):
        await run_process(["sleep", "5"], timeout=0.1)


@pytest.mark.asyncio
async def test_run_process_error():
    with pytest.raises(ProcessError, match="command failed"):
        await run_process(["ls", "/nonexistent_path_jarvis_test_xyz"])


@pytest.mark.asyncio
async def test_run_process_empty_args():
    with pytest.raises(ValueError, match="args cannot be empty"):
        await run_process([])
