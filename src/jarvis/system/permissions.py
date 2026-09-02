from __future__ import annotations

import os
from pathlib import Path


class PermissionErrorInfo(RuntimeError):
    pass


def require_readable(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    if not os.access(path, os.R_OK):
        raise PermissionErrorInfo(f"file is not readable: {path}")


def require_writable(path: Path) -> None:
    target = path if path.exists() else path.parent
    if not target.exists():
        raise FileNotFoundError(target)
    if not os.access(target, os.W_OK):
        raise PermissionErrorInfo(f"path is not writable: {target}")
