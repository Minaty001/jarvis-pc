import os
import tempfile
from pathlib import Path


def atomic_write_text(
    path: str | Path,
    content: str,
    mode: int = 0o600,
    encoding: str = "utf-8",
) -> Path:
    """Write content to path atomically using a temporary file.

    Creates parent directories if they do not exist. Sets permission mode.
    """
    target_path = Path(path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_filepath = tempfile.mkstemp(
        dir=target_path.parent,
        prefix=f".{target_path.name}.",
        suffix=".tmp",
    )
    temp_path = Path(temp_filepath)
    closed = False
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        closed = True
        os.replace(temp_path, target_path)
    except Exception:
        if not closed:
            try:
                os.close(fd)
            except OSError:
                pass
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise

    return target_path
