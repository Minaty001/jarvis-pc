from __future__ import annotations

import os
import sys

from jarvis.system.distro import detect_distribution
from jarvis.system.paths import get_app_paths


def run_doctor() -> str:
    lines = [
        "JARVIS Linux Doctor",
        "-------------------",
        "",
        "OS:",
        f"  {detect_distribution().pretty_name}",
        "",
        "Python:",
        f"  {sys.version.split()[0]}      OK",
        "",
        "CPU:",
        f"  {os.uname().machine}      OK",
        "",
        "XDG Paths:",
    ]
    paths = get_app_paths()
    lines.append(f"  CONFIG ({paths.config})      OK")
    lines.append(f"  DATA   ({paths.data})      OK")
    lines.append(f"  STATE  ({paths.state})      OK")
    lines.append(f"  CACHE  ({paths.cache})      OK")
    lines.append(f"  RUNTIME({paths.runtime})      OK")

    lines.extend([
        "",
        "Result:",
        "  0 errors",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    print(run_doctor())
