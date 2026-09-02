"""
JARVIS PC — Main Entry Point.
Delegates execution to jarvis.cli.main.run_cli().
"""
from __future__ import annotations

import sys
from jarvis.cli.main import run_cli


def main() -> None:
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
