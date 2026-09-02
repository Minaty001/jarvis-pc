import pytest
from pathlib import Path
from jarvis.tools.builtin.filesystem import SafeFileStore, PathSecurityError


def test_safe_file_store_rejects_escape(tmp_path: Path) -> None:
    store = SafeFileStore(tmp_path)
    with pytest.raises(PathSecurityError):
        store.resolve_user_path("../../etc/passwd")


def test_safe_file_store_valid_read(tmp_path: Path) -> None:
    f = tmp_path / "valid.txt"
    f.write_text("hello world")
    store = SafeFileStore(tmp_path)
    content = store.read_text("valid.txt")
    assert content == "hello world"


def test_safe_file_store_nested_path(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    f = nested / "item.json"
    f.write_text('{"nested": true}')
    store = SafeFileStore(tmp_path)
    resolved = store.resolve_user_path("a/b/item.json")
    assert resolved == f.resolve()
    assert store.read_text("a/b/item.json") == '{"nested": true}'
