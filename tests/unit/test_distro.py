import pytest
from jarvis.system.distro import detect_distribution, LinuxDistribution
from jarvis.system.permissions import require_readable, require_writable, PermissionErrorInfo


def test_detect_distribution():
    distro = detect_distribution()
    assert isinstance(distro, LinuxDistribution)
    assert distro.id != ""


def test_permission_checks(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    require_readable(f)
    require_writable(f)

    non_existent = tmp_path / "non_existent.txt"
    with pytest.raises(FileNotFoundError):
        require_readable(non_existent)

    non_existent_dir_file = tmp_path / "no_dir" / "file.txt"
    with pytest.raises(FileNotFoundError):
        require_writable(non_existent_dir_file)
