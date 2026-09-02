from unittest.mock import AsyncMock, patch
import pytest

from jarvis.tools.builtin.applications import ApplicationError, open_application
from jarvis.tools.builtin.processes import find_processes


@pytest.mark.asyncio
async def test_open_application_disallowed():
    with pytest.raises(ApplicationError, match="not allowed"):
        await open_application("unauthorized_app_xyz")


@pytest.mark.asyncio
async def test_open_application_allowed():
    with patch("jarvis.tools.builtin.applications.run_process", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = AsyncMock(returncode=0, stdout="", stderr="")
        res = await open_application("firefox")
        mock_run.assert_called_once_with(["firefox"], timeout=10.0)


def test_find_processes():
    procs = find_processes("python3")
    assert isinstance(procs, list)
