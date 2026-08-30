"""Camera — Capture photos from webcam.
Auto-requests camera permission on Linux via V4L2.
"""

import os
import time
import subprocess
import glob
from pathlib import Path
from typing import Any

from config.logger import get_logger
from config.settings import settings

logger = get_logger("tools.camera")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    logger.warning("opencv-python not installed. Camera tool disabled.")


def _ensure_camera_permission() -> bool:
    """Auto-grant camera permission by checking V4L2 access."""
    video_devices = glob.glob("/dev/video*")
    if not video_devices:
        logger.warning("No camera devices found (/dev/video*)")
        return False

    # Check read permission on first device
    if os.access(video_devices[0], os.R_OK | os.W_OK):
        logger.info("Camera permission granted: %s", video_devices[0])
        return True

    # Try adding user to video group
    try:
        username = os.getenv("USER")
        if username:
            subprocess.run(
                ["sudo", "usermod", "-aG", "video", username],
                capture_output=True, timeout=5,
            )
            logger.info("Added user '%s' to video group (re-login may be needed)", username)
    except Exception:
        pass

    # Fallback: check if we can still open with OpenCV
    if HAS_CV2:
        try:
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                cap.release()
                logger.info("Camera accessible via OpenCV")
                return True
        except Exception:
            pass

    logger.warning("Camera permission denied for %s", video_devices)
    return False


def take_photo(camera_index: int = 0) -> dict[str, Any]:
    """Capture a single photo from the webcam."""
    if not HAS_CV2:
        return {"success": False, "result": "opencv-python not installed. Run: pip install opencv-python"}

    if not _ensure_camera_permission():
        return {"success": False, "result": "Camera permission denied. Check /dev/video* access."}

    output_dir = settings.data_dir / "camera"
    output_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"photo_{timestamp}.png"

    try:
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            return {"success": False, "result": f"Cannot open camera {camera_index}"}

        # Warm up camera
        for _ in range(10):
            cap.read()

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return {"success": False, "result": "Failed to capture frame from camera"}

        cv2.imwrite(str(output_path), frame)
        height, width = frame.shape[:2]
        msg = f"Photo saved: {output_path} ({width}x{height})"
        logger.info(msg)
        return {"success": True, "result": msg, "path": str(output_path), "width": width, "height": height}

    except Exception as e:
        msg = f"Camera capture failed: {e}"
        logger.error(msg)
        return {"success": False, "result": msg}


def take_photo_sequence(count: int = 5, delay: float = 1.0, camera_index: int = 0) -> dict[str, Any]:
    """Capture multiple photos with a delay between each."""
    if not HAS_CV2:
        return {"success": False, "result": "opencv-python not installed"}

    if not _ensure_camera_permission():
        return {"success": False, "result": "Camera permission denied"}

    count = min(max(count, 1), 20)  # Limit 1-20
    output_dir = settings.data_dir / "camera"
    output_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    try:
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            return {"success": False, "result": f"Cannot open camera {camera_index}"}

        # Warm up
        for _ in range(10):
            cap.read()

        saved = []
        for i in range(count):
            ret, frame = cap.read()
            if ret and frame is not None:
                path = output_dir / f"seq_{timestamp}_{i+1:03d}.png"
                cv2.imwrite(str(path), frame)
                saved.append(str(path))
            if i < count - 1:
                time.sleep(delay)

        cap.release()
        msg = f"Captured {len(saved)}/{count} photos"
        logger.info(msg)
        return {"success": True, "result": msg, "paths": saved, "count": len(saved)}

    except Exception as e:
        msg = f"Camera sequence failed: {e}"
        logger.error(msg)
        return {"success": False, "result": msg}


def record_video(duration: float = 5.0, camera_index: int = 0) -> dict[str, Any]:
    """Record a short video clip."""
    if not HAS_CV2:
        return {"success": False, "result": "opencv-python not installed"}

    if not _ensure_camera_permission():
        return {"success": False, "result": "Camera permission denied"}

    duration = min(max(duration, 1.0), 30.0)  # Limit 1-30 seconds
    output_dir = settings.data_dir / "camera"
    output_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"video_{timestamp}.avi"

    try:
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            return {"success": False, "result": f"Cannot open camera {camera_index}"}

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 20.0

        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

        start = time.time()
        frames = 0
        while time.time() - start < duration:
            ret, frame = cap.read()
            if ret:
                out.write(frame)
                frames += 1
            else:
                break

        cap.release()
        out.release()

        actual_duration = frames / fps if fps > 0 else 0
        msg = f"Video saved: {output_path} ({frames} frames, {actual_duration:.1f}s)"
        logger.info(msg)
        return {"success": True, "result": msg, "path": str(output_path), "frames": frames, "duration": actual_duration}

    except Exception as e:
        msg = f"Video recording failed: {e}"
        logger.error(msg)
        return {"success": False, "result": msg}


def list_cameras() -> dict[str, Any]:
    """List available camera devices."""
    video_devices = glob.glob("/dev/video*")
    has_permission = _ensure_camera_permission() if video_devices else False

    # Determine max index from /dev/video* devices
    max_index = 0
    for dev in video_devices:
        try:
            idx = int(dev.replace("/dev/video", ""))
            max_index = max(max_index, idx + 1)
        except ValueError:
            pass
    max_index = max(max_index, 1)

    cameras = []
    if HAS_CV2 and has_permission:
        for i in range(min(max_index, 5)):  # Cap at 5 to avoid spam
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                cameras.append({
                    "index": i,
                    "resolution": f"{width}x{height}",
                    "working": ret,
                })

    return {
        "success": True,
        "result": f"Found {len(cameras)} camera(s)" if cameras else "No cameras found",
        "cameras": cameras,
        "devices": video_devices,
        "permission": has_permission,
    }
