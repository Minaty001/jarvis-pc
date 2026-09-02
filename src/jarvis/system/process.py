from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass
from typing import Sequence


class ProcessError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


async def run_process(
    args: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    timeout: float = 30.0,
    env: dict[str, str] | None = None,
) -> ProcessResult:
    if not args:
        raise ValueError("args cannot be empty")

    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except OSError:
            pass

        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            await process.wait()

        raise ProcessError(f"process timed out after {timeout}s")

    result = ProcessResult(
        returncode=process.returncode if process.returncode is not None else -1,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )

    if result.returncode != 0:
        raise ProcessError(
            f"command failed ({result.returncode}): {result.stderr[:1000]}"
        )

    return result
