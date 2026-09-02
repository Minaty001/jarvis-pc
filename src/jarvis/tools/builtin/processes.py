from __future__ import annotations

import psutil


def find_processes(name: str) -> list[dict]:
    result: list[dict] = []
    for process in psutil.process_iter(["pid", "name", "username"]):
        try:
            info = process.info
            if info.get("name") == name:
                result.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return result
