from __future__ import annotations

import psutil


def find_processes(name: str | None = None, limit: int = 50) -> list[dict]:
    """List matching processes; with no name, summarize the full set."""
    result: list[dict] = []
    for process in psutil.process_iter(["pid", "name", "username"]):
        try:
            info = process.info
            if name is not None and info.get("name") != name:
                continue
            result.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    if name is not None:
        return result
    return [{"total": len(result)}, {"sample": result[:limit]}]
