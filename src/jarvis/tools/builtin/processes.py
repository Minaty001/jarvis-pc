from __future__ import annotations

import psutil


def find_processes(name: str | None = None, limit: int = 50) -> list[dict]:
    """List matching processes; with no name, summarize the full set."""
    procs: list[dict] = []
    for process in psutil.process_iter(["pid", "name", "username"]):
        try:
            if name is None or process.info.get("name") == name:
                procs.append(process.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return procs if name is not None else [{"total": len(procs)}, {"sample": procs[:limit]}]
