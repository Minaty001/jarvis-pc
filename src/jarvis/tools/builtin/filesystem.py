from pathlib import Path
from jarvis.system.files import atomic_write_text


class PathSecurityError(Exception):
    """Raised when a path escapes the allowed root directory."""
    pass


class SafeFileStore:
    """Provides path-traversal secure file access within a root directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def resolve_user_path(self, user_path: str | Path) -> Path:
        p = Path(user_path)
        if p.is_absolute():
            candidate = p.resolve()
        else:
            candidate = (self.root / p).resolve()

        if not candidate.is_relative_to(self.root):
            raise PathSecurityError(
                f"Path security error: path '{user_path}' escapes root directory '{self.root}'"
            )

        return candidate

    def read_text(self, user_path: str | Path, encoding: str = "utf-8") -> str:
        target = self.resolve_user_path(user_path)
        return target.read_text(encoding=encoding)

    def write_text(
        self,
        user_path: str | Path,
        content: str,
        mode: int = 0o600,
        encoding: str = "utf-8",
    ) -> Path:
        target = self.resolve_user_path(user_path)
        return atomic_write_text(target, content, mode=mode, encoding=encoding)
