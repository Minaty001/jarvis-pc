from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LinuxDistribution:
    id: str
    version_id: str
    pretty_name: str


def detect_distribution() -> LinuxDistribution:
    path = Path("/etc/os-release")
    values: dict[str, str] = {}

    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    except OSError:
        return LinuxDistribution(
            id="unknown",
            version_id="unknown",
            pretty_name="Unknown Linux",
        )

    return LinuxDistribution(
        id=values.get("ID", "unknown"),
        version_id=values.get("VERSION_ID", "unknown"),
        pretty_name=values.get("PRETTY_NAME", "Unknown Linux"),
    )
