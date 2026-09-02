import os
from pathlib import Path
from unittest.mock import patch

import pytest

from jarvis.tools.builtin.media import CameraPermissionError, check_camera_permissions


def test_camera_no_sudo_in_source():
    media_file = Path("src/jarvis/tools/builtin/media.py")
    assert media_file.exists()
    assert "sudo" not in media_file.read_text()


def test_camera_permissions_nonexistent_device():
    assert check_camera_permissions("/dev/video9999") is False


def test_camera_permissions_permission_denied():
    with patch("os.path.exists", return_value=True), patch("os.access", return_value=False):
        with pytest.raises(CameraPermissionError) as exc_info:
            check_camera_permissions("/dev/video0")
        assert "Permission denied" in str(exc_info.value)
        assert "/dev/video0" in str(exc_info.value)


def test_camera_permissions_success():
    with patch("os.path.exists", return_value=True), patch("os.access", return_value=True):
        assert check_camera_permissions("/dev/video0") is True
