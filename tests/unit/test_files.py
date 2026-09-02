import pytest
from pathlib import Path
from jarvis.system.files import atomic_write_text


def test_atomic_write_text(tmp_path: Path) -> None:
    target = tmp_path / "config" / "settings.json"
    atomic_write_text(target, '{"key": "value"}', mode=0o600)
    assert target.exists()
    assert target.read_text() == '{"key": "value"}'
    assert oct(target.stat().st_mode)[-3:] == "600"


def test_atomic_write_text_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "data.txt"
    target.write_text("old content")
    atomic_write_text(target, "new content", mode=0o644)
    assert target.read_text() == "new content"
    assert oct(target.stat().st_mode)[-3:] == "644"
