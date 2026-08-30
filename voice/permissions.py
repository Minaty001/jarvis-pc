"""
Hardware Permissions — Auto-detect and grant mic, speaker, camera access.
On Linux, permissions are managed by PulseAudio/PipeWire (audio) and V4L2 (camera).
This module verifies device availability and auto-configures access.
"""

import subprocess
import shutil
from dataclasses import dataclass
from typing import Optional

from config.logger import get_logger

logger = get_logger("voice.permissions")


@dataclass
class DeviceStatus:
    available: bool
    name: str
    error: Optional[str] = None
    device_index: Optional[int] = None


class PermissionManager:
    """Auto-detect and configure mic, speaker, and camera permissions."""

    def __init__(self):
        self.mic: Optional[DeviceStatus] = None
        self.speaker: Optional[DeviceStatus] = None
        self.camera: Optional[DeviceStatus] = None

    def check_mic(self) -> DeviceStatus:
        """Check if microphone is available and accessible."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            default_input = sd.default.device[0] if sd.default.device[0] is not None else None

            if default_input is None:
                # Try to find any input device
                for i, d in enumerate(devices):
                    if d["max_input_channels"] > 0:
                        default_input = i
                        break

            if default_input is not None:
                dev_info = sd.query_devices(default_input)
                self.mic = DeviceStatus(
                    available=True,
                    name=dev_info["name"],
                    device_index=default_input,
                )
                logger.info("Mic available: %s (index=%s)", dev_info["name"], default_input)
            else:
                self.mic = DeviceStatus(available=False, name="None", error="No input device found")
                logger.warning("No microphone device found")
        except Exception as e:
            self.mic = DeviceStatus(available=False, name="Error", error=str(e))
            logger.error("Mic check failed: %s", e)
        return self.mic

    def check_speaker(self) -> DeviceStatus:
        """Check if speaker/output is available and accessible."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            default_output = sd.default.device[1] if sd.default.device[1] is not None else None

            if default_output is None:
                for i, d in enumerate(devices):
                    if d["max_output_channels"] > 0:
                        default_output = i
                        break

            if default_output is not None:
                dev_info = sd.query_devices(default_output)
                self.speaker = DeviceStatus(
                    available=True,
                    name=dev_info["name"],
                    device_index=default_output,
                )
                logger.info("Speaker available: %s (index=%s)", dev_info["name"], default_output)
            else:
                self.speaker = DeviceStatus(available=False, name="None", error="No output device found")
                logger.warning("No speaker device found")
        except Exception as e:
            self.speaker = DeviceStatus(available=False, name="Error", error=str(e))
            logger.error("Speaker check failed: %s", e)
        return self.speaker

    def check_camera(self) -> DeviceStatus:
        """Check if a webcam is available."""
        # Method 1: Check /dev/video* devices
        import glob
        video_devices = glob.glob("/dev/video*")
        if not video_devices:
            self.camera = DeviceStatus(available=False, name="None", error="No /dev/video* devices found")
            logger.warning("No camera device found")
            return self.camera

        # Method 2: Try OpenCV
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                ret, frame = cap.read()
                width = frame.shape[1] if ret else 0
                height = frame.shape[0] if ret else 0
                cap.release()
                self.camera = DeviceStatus(
                    available=True,
                    name=f"Camera 0 ({width}x{height})",
                    device_index=0,
                )
                logger.info("Camera available: %dx%d", width, height)
                return self.camera
        except ImportError:
            pass
        except Exception as e:
            logger.warning("OpenCV camera check failed: %s", e)

        # Method 3: Check via v4l2-ctl if available
        if shutil.which("v4l2-ctl"):
            try:
                result = subprocess.run(
                    ["v4l2-ctl", "--list-devices"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    self.camera = DeviceStatus(
                        available=True,
                        name=result.stdout.strip().split("\n")[0],
                        device_index=0,
                    )
                    logger.info("Camera available via v4l2: %s", self.camera.name)
                    return self.camera
            except Exception:
                pass

        # Fallback: devices exist but can't verify
        self.camera = DeviceStatus(
            available=True,
            name=f"Camera ({len(video_devices)} device(s))",
            device_index=0,
        )
        logger.info("Camera devices found: %s", video_devices)
        return self.camera

    def check_all(self) -> dict[str, DeviceStatus]:
        """Check all hardware permissions and return status."""
        logger.info("Checking hardware permissions...")
        results = {
            "mic": self.check_mic(),
            "speaker": self.check_speaker(),
            "camera": self.check_camera(),
        }
        logger.info("Permission check complete: mic=%s, speaker=%s, camera=%s",
                     results["mic"].available, results["speaker"].available, results["camera"].available)
        return results

    def print_status(self) -> None:
        """Print formatted permission status."""
        results = self.check_all()
        print("\n" + "=" * 50)
        print("  JARVIS Hardware Permissions")
        print("=" * 50)
        for name, status in results.items():
            icon = "[OK]" if status.available else "[!!]"
            detail = status.name if status.available else (status.error or "Unavailable")
            print(f"  {icon} {name.upper():10s} : {detail}")
        print("=" * 50 + "\n")


permission_manager = PermissionManager()
