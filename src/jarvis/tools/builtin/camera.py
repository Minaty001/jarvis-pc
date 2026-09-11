"""
Hardware camera discovery and photo capture utilities for Linux Mint / Ubuntu.
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.system.process import run_process
from jarvis.tools.builtin.media import CameraPermissionError, check_camera_permissions

logger = logging.getLogger(__name__)


def list_cameras() -> list[dict[str, Any]]:
    """Discover available camera/video capture devices on the system.

    Returns:
        List of dictionaries with device path, hardware name, and accessibility status.
    """
    cameras: list[dict[str, Any]] = []
    sysfs_nodes = sorted(glob.glob("/sys/class/video4linux/video*"))

    if sysfs_nodes:
        for node in sysfs_nodes:
            dev_name = Path(node).name
            dev_path = f"/dev/{dev_name}"
            name_file = Path(node) / "name"
            camera_name = dev_name
            if name_file.exists():
                try:
                    camera_name = name_file.read_text(encoding="utf-8").strip()
                except OSError:
                    pass

            accessible = False
            try:
                accessible = check_camera_permissions(dev_path)
            except (CameraPermissionError, OSError):
                accessible = False

            cameras.append({
                "device": dev_path,
                "name": camera_name,
                "accessible": accessible,
            })
    else:
        # Fallback to probing /dev/video0 through /dev/video4
        for idx in range(5):
            dev_path = f"/dev/video{idx}"
            if Path(dev_path).exists():
                accessible = False
                try:
                    accessible = check_camera_permissions(dev_path)
                except (CameraPermissionError, OSError):
                    accessible = False

                cameras.append({
                    "device": dev_path,
                    "name": f"Video Device {idx}",
                    "accessible": accessible,
                })

    return cameras


async def take_photo(
    output_path: str | None = None,
    device_path: str = "/dev/video0",
) -> str:
    """Capture a single photo frame from a camera device.

    Args:
        output_path: Destination image path (must be within user's home). If omitted,
                     saves to ~/Pictures/jarvis_captures/capture_YYYYMMDD_HHMMSS.jpg.
        device_path: V4L2 camera device path (default: /dev/video0).

    Returns:
        Confirmation message with the absolute path and size of the saved image.

    Raises:
        ValueError: If output path is outside user's home directory.
        FileNotFoundError: If the specified camera device does not exist.
        CameraPermissionError: If user lacks permission to access the camera device.
        RuntimeError: If image capture fails across all available capture backends.
    """
    dev = Path(device_path)
    if not dev.exists():
        raise FileNotFoundError(f"Camera device '{device_path}' does not exist.")

    # Check permission
    check_camera_permissions(device_path)

    # Determine destination path
    home = Path.home().resolve()
    if output_path:
        target = Path(output_path).expanduser().resolve()
        try:
            target.relative_to(home)
        except ValueError:
            raise ValueError(
                f"Invalid output path '{output_path}'. Photos must be saved within your home directory ({home})."
            )
    else:
        pictures_dir = home / "Pictures" / "jarvis_captures"
        pictures_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = pictures_dir / f"capture_{timestamp}.jpg"

    target.parent.mkdir(parents=True, exist_ok=True)

    # Select available capture backend in priority order: gst-launch-1.0 -> ffmpeg -> fswebcam
    backends: list[list[str]] = []
    if shutil.which("gst-launch-1.0"):
        backends.append([
            "gst-launch-1.0",
            "v4l2src",
            f"device={device_path}",
            "num-buffers=1",
            "!",
            "videoconvert",
            "!",
            "jpegenc",
            "!",
            "filesink",
            f"location={target}",
        ])
    if shutil.which("ffmpeg"):
        backends.append([
            "ffmpeg",
            "-y",
            "-f",
            "v4l2",
            "-i",
            device_path,
            "-frames:v",
            "1",
            str(target),
        ])
    if shutil.which("fswebcam"):
        backends.append([
            "fswebcam",
            "-d",
            device_path,
            "-r",
            "1280x720",
            "--no-banner",
            str(target),
        ])

    if not backends:
        raise RuntimeError(
            "No camera capture backend found on this system. Please install gstreamer1.0-tools, ffmpeg, or fswebcam."
        )

    last_error: str | None = None
    for cmd in backends:
        backend_name = cmd[0]
        try:
            logger.debug("Attempting photo capture with %s on %s...", backend_name, device_path)
            res = await run_process(cmd, timeout=15.0)
            if res.returncode == 0 and target.exists() and target.stat().st_size > 0:
                size_kb = target.stat().st_size / 1024.0
                return f"Photo captured successfully from {device_path} and saved to {target} ({size_kb:.1f} KB)."
            last_error = res.stderr or f"Returncode {res.returncode}"
        except Exception as exc:
            last_error = str(exc)
            logger.warning("Backend %s failed: %s", backend_name, exc)

    raise RuntimeError(f"Failed to capture photo from {device_path}. Last error: {last_error}")
