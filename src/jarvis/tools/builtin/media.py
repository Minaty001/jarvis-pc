"""
Media and Camera device utilities.
"""

import os
from pathlib import Path


class CameraPermissionError(PermissionError):
    """Raised when access to a camera device is denied due to system permissions."""

    pass


def check_camera_permissions(device_path: str = "/dev/video0") -> bool:
    """Check permissions for a camera device.

    Args:
        device_path: Path to the video device file (default: "/dev/video0").

    Returns:
        True if the device exists and is accessible.
        False if the device does not exist.

    Raises:
        CameraPermissionError: If the device exists but permission is denied.
    """
    path = Path(device_path)
    if not path.exists():
        return False

    if not os.access(path, os.R_OK | os.W_OK):
        raise CameraPermissionError(
            f"Permission denied accessing camera device '{device_path}'. "
            "Please ensure current user has access rights (e.g. member of 'video' group)."
        )

    return True
