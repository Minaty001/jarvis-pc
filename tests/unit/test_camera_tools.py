"""
Unit tests for camera discovery and photo capture tools.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from jarvis.system.process import ProcessResult
from jarvis.tools.builtin.camera import list_cameras, take_photo
from jarvis.tools.builtin.media import CameraPermissionError


def test_list_cameras_sysfs(tmp_path: Path):
    # Mock sysfs video device directory
    sysfs_dir = tmp_path / "sys_class_v4l"
    video0_dir = sysfs_dir / "video0"
    video0_dir.mkdir(parents=True)
    (video0_dir / "name").write_text("Test HD Webcam\n")

    with patch("glob.glob", return_value=[str(video0_dir)]), \
         patch("jarvis.tools.builtin.camera.check_camera_permissions", return_value=True):
        cameras = list_cameras()

    assert len(cameras) == 1
    assert cameras[0]["device"] == "/dev/video0"
    assert cameras[0]["name"] == "Test HD Webcam"
    assert cameras[0]["accessible"] is True


def test_list_cameras_fallback():
    with patch("glob.glob", return_value=[]), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("jarvis.tools.builtin.camera.check_camera_permissions", return_value=True):
        cameras = list_cameras()

    assert len(cameras) == 5
    assert cameras[0]["device"] == "/dev/video0"
    assert cameras[0]["accessible"] is True


@pytest.mark.asyncio
async def test_take_photo_device_not_found():
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError, match="does not exist"):
            await take_photo(device_path="/dev/video999")


@pytest.mark.asyncio
async def test_take_photo_permission_denied():
    with patch("pathlib.Path.exists", return_value=True), \
         patch("jarvis.tools.builtin.camera.check_camera_permissions", side_effect=CameraPermissionError("denied")):
        with pytest.raises(CameraPermissionError):
            await take_photo(device_path="/dev/video0")


@pytest.mark.asyncio
async def test_take_photo_invalid_output_path():
    with patch("pathlib.Path.exists", return_value=True), \
         patch("jarvis.tools.builtin.camera.check_camera_permissions", return_value=True):
        with pytest.raises(ValueError, match="must be saved within your home directory"):
            await take_photo(output_path="/etc/passwd", device_path="/dev/video0")


@pytest.mark.asyncio
async def test_take_photo_success(tmp_path: Path):
    target_img = tmp_path / "snap.jpg"

    def mock_run_process(cmd, timeout=15.0):
        # Simulate successful creation of image file
        target_img.write_bytes(b"\xff\xd8\xff\xe0test_jpeg_bytes")
        return ProcessResult(returncode=0, stdout="", stderr="")

    # Patch home to tmp_path so target_img is inside home
    with patch("pathlib.Path.home", return_value=tmp_path), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("jarvis.tools.builtin.camera.check_camera_permissions", return_value=True), \
         patch("jarvis.tools.builtin.camera.run_process", side_effect=mock_run_process):
        res = await take_photo(output_path=str(target_img), device_path="/dev/video0")

    assert "Photo captured successfully" in res
    assert str(target_img) in res
