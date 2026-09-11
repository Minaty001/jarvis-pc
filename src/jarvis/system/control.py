"""Linux System & Hardware Subsystem Controller.

Manages audio volume/mute, display brightness, bluetooth devices,
Wi-Fi networking, power/session states, and application processes.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess  # nosec B404
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger(__name__)


def _run_cmd(args: List[str], timeout: float = 8.0) -> Tuple[bool, str]:
    """Execute command safely with strict argument lists."""
    bin_name = args[0]
    bin_path = shutil.which(bin_name)
    if not bin_path:
        return False, f"Command '{bin_name}' not available on this system."

    full_args = [bin_path] + args[1:]
    try:
        proc = subprocess.run(  # nosec B603
            full_args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = proc.stdout.strip() if proc.returncode == 0 else proc.stderr.strip()
        return proc.returncode == 0, output
    except Exception as exc:
        logger.debug("Command execution error %s: %s", args, exc)
        return False, str(exc)


class AudioController:
    """Controls volume and mute state via pactl, amixer, or wpctl."""

    def get_volume(self) -> Dict[str, Any]:
        """Query default sink volume and mute status."""
        # 1. Try pactl
        ok, out = _run_cmd(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        if ok and out:
            match = re.search(r"(\d+)%", out)
            vol = int(match.group(1)) if match else 50
            ok_mute, out_mute = _run_cmd(["pactl", "get-sink-mute", "@DEFAULT_SINK@"])
            is_muted = "yes" in out_mute.lower() if ok_mute else False
            return {"percent": vol, "muted": is_muted, "backend": "pactl"}

        # 2. Try amixer
        ok, out = _run_cmd(["amixer", "get", "Master"])
        if ok and out:
            match = re.search(r"\[(\d+)%\]", out)
            vol = int(match.group(1)) if match else 50
            is_muted = "[off]" in out.lower()
            return {"percent": vol, "muted": is_muted, "backend": "amixer"}

        # 3. Try wpctl (PipeWire)
        ok, out = _run_cmd(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        if ok and out:
            match = re.search(r"Volume:\s*([\d\.]+)", out)
            vol = int(float(match.group(1)) * 100) if match else 50
            is_muted = "[MUTED]" in out
            return {"percent": vol, "muted": is_muted, "backend": "wpctl"}

        return {"percent": 50, "muted": False, "backend": "simulated"}

    def set_volume(self, percent: int) -> bool:
        """Set volume percentage (clamped to 0-100%)."""
        clamped = max(0, min(100, int(percent)))

        # 1. Try pactl
        ok, _ = _run_cmd(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{clamped}%"])
        if ok:
            return True

        # 2. Try amixer
        ok, _ = _run_cmd(["amixer", "set", "Master", f"{clamped}%"])
        if ok:
            return True

        # 3. Try wpctl
        ok, _ = _run_cmd(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{clamped / 100.0:.2f}"])
        return ok

    def set_mute(self, muted: bool) -> bool:
        """Set mute state."""
        mute_arg = "1" if muted else "0"

        # 1. Try pactl
        ok, _ = _run_cmd(["pactl", "set-sink-mute", "@DEFAULT_SINK@", mute_arg])
        if ok:
            return True

        # 2. Try amixer
        state_str = "mute" if muted else "unmute"
        ok, _ = _run_cmd(["amixer", "set", "Master", state_str])
        if ok:
            return True

        # 3. Try wpctl
        ok, _ = _run_cmd(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", mute_arg])
        return ok


class BrightnessController:
    """Controls screen brightness via brightnessctl or xrandr."""

    def get_brightness(self) -> Dict[str, Any]:
        """Get current display brightness percentage."""
        # 1. Try brightnessctl
        ok, out = _run_cmd(["brightnessctl", "-m"])
        if ok and out:
            parts = out.split(",")
            if len(parts) >= 4:
                pct_str = parts[3].replace("%", "").strip()
                try:
                    pct = int(pct_str)
                    return {"percent": pct, "backend": "brightnessctl"}
                except ValueError:
                    pass

        # 2. Try reading /sys/class/backlight
        try:
            bl_dir = Path("/sys/class/backlight")
            if bl_dir.exists():
                for dev in bl_dir.iterdir():
                    cur_f = dev / "brightness"
                    max_f = dev / "max_brightness"
                    if cur_f.exists() and max_f.exists():
                        cur_val = int(cur_f.read_text().strip())
                        max_val = int(max_f.read_text().strip())
                        if max_val > 0:
                            pct = int((cur_val / max_val) * 100)
                            return {"percent": pct, "backend": "sysfs"}
        except Exception:
            pass

        return {"percent": 100, "backend": "simulated"}

    def set_brightness(self, percent: int) -> bool:
        """Set screen brightness (clamped to 5-100% to prevent black screen)."""
        clamped = max(5, min(100, int(percent)))

        # 1. Try brightnessctl
        ok, _ = _run_cmd(["brightnessctl", "set", f"{clamped}%"])
        if ok:
            return True

        # 2. Try xrandr brightness
        try:
            factor = clamped / 100.0
            ok_xr, out_xr = _run_cmd(["xrandr", "--current"])
            if ok_xr and out_xr:
                match = re.search(r"^(\S+)\s+connected", out_xr, re.MULTILINE)
                if match:
                    disp = match.group(1)
                    ok_set, _ = _run_cmd(["xrandr", "--output", disp, "--brightness", str(factor)])
                    return ok_set
        except Exception:
            pass

        return False


class BluetoothController:
    """Controls Bluetooth power and device connections via bluetoothctl."""

    def list_devices(self) -> List[Dict[str, str]]:
        """List paired and available Bluetooth devices."""
        devices = []
        ok, out = _run_cmd(["bluetoothctl", "devices"])
        if ok and out:
            for line in out.splitlines():
                parts = line.split(" ", 2)
                if len(parts) >= 3 and parts[0] == "Device":
                    devices.append({"mac": parts[1], "name": parts[2]})
        return devices

    def set_power(self, enabled: bool) -> bool:
        """Turn Bluetooth radio on or off."""
        state = "on" if enabled else "off"
        ok, _ = _run_cmd(["bluetoothctl", "power", state])
        return ok

    def connect_device(self, device: str) -> bool:
        """Connect to a Bluetooth device by MAC address or name."""
        mac = device.strip()
        if not re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", mac):
            # Resolve name to MAC
            for d in self.list_devices():
                if device.lower() in d["name"].lower():
                    mac = d["mac"]
                    break
        ok, _ = _run_cmd(["bluetoothctl", "connect", mac])
        return ok

    def disconnect_device(self, device: str) -> bool:
        """Disconnect a Bluetooth device."""
        mac = device.strip()
        if not re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", mac):
            for d in self.list_devices():
                if device.lower() in d["name"].lower():
                    mac = d["mac"]
                    break
        ok, _ = _run_cmd(["bluetoothctl", "disconnect", mac])
        return ok


class NetworkController:
    """Controls and monitors Wi-Fi and network connectivity via nmcli / psutil."""

    def get_status(self) -> Dict[str, Any]:
        """Query active network connections and IP addresses."""
        ssid = None
        iface = None

        # 1. Try nmcli
        ok, out = _run_cmd(["nmcli", "-t", "-f", "ACTIVE,SSID,DEVICE", "dev", "wifi"])
        if ok and out:
            for line in out.splitlines():
                if line.startswith("yes:"):
                    parts = line.split(":")
                    if len(parts) >= 3:
                        ssid = parts[1]
                        iface = parts[2]
                        break

        # 2. Get IP address
        primary_ip = "127.0.0.1"
        try:
            addrs = psutil.net_if_addrs()
            for if_name, addr_list in addrs.items():
                if if_name == "lo":
                    continue
                for addr in addr_list:
                    if addr.family.name == "AF_INET":
                        primary_ip = addr.address
                        if not iface:
                            iface = if_name
                        break
        except Exception:
            pass

        return {
            "connected": primary_ip != "127.0.0.1",
            "ssid": ssid or "Ethernet / Local Network",
            "ip": primary_ip,
            "interface": iface or "eth0",
        }

    def list_wifi(self) -> List[Dict[str, str]]:
        """Scan available Wi-Fi access points."""
        networks = []
        ok, out = _run_cmd(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"])
        if ok and out:
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) >= 3 and parts[0]:
                    networks.append(
                        {
                            "ssid": parts[0],
                            "signal": parts[1],
                            "security": parts[2] or "Open",
                        }
                    )
        return networks

    def set_wifi_power(self, enabled: bool) -> bool:
        """Enable or disable Wi-Fi radio."""
        state = "on" if enabled else "off"
        ok, _ = _run_cmd(["nmcli", "radio", "wifi", state])
        return ok


class PowerController:
    """Controls session lock, suspend, reboot, and poweroff states."""

    def lock_session(self) -> bool:
        """Lock active user desktop session."""
        # 1. Try loginctl
        ok, _ = _run_cmd(["loginctl", "lock-session"])
        if ok:
            return True
        # 2. Try xdg-screensaver
        ok_xdg, _ = _run_cmd(["xdg-screensaver", "lock"])
        return ok_xdg

    def suspend(self) -> bool:
        """Suspend system to RAM."""
        ok, _ = _run_cmd(["systemctl", "suspend"])
        return ok

    def reboot(self) -> bool:
        """Reboot the operating system."""
        ok, _ = _run_cmd(["systemctl", "reboot"])
        return ok

    def poweroff(self) -> bool:
        """Shutdown computer power."""
        ok, _ = _run_cmd(["systemctl", "poweroff"])
        return ok


class ProcessController:
    """Finds and terminates application processes or desktop windows."""

    def kill_process(self, target: str | int, force: bool = False) -> Dict[str, Any]:
        """Terminate process by PID or name."""
        killed = 0
        pids = []

        # Target is numeric PID
        if isinstance(target, int) or (isinstance(target, str) and target.isdigit()):
            pid = int(target)
            try:
                p = psutil.Process(pid)
                if force:
                    p.kill()
                else:
                    p.terminate()
                return {"success": True, "killed": 1, "pids": [pid], "target": str(pid)}
            except Exception as exc:
                return {"success": False, "killed": 0, "pids": [], "error": str(exc)}

        # Target is process name
        target_name = str(target).lower().strip()
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if target_name in p.info["name"].lower():
                    if force:
                        p.kill()
                    else:
                        p.terminate()
                    pids.append(p.info["pid"])
                    killed += 1
            except Exception:
                continue

        return {
            "success": killed > 0,
            "killed": killed,
            "pids": pids,
            "target": target_name,
        }

    def close_window(self, title_or_id: str) -> bool:
        """Close desktop window by title or hex ID."""
        # Try wmctrl
        ok, _ = _run_cmd(["wmctrl", "-c", title_or_id])
        if ok:
            return True
        # Try xdotool
        ok_xd, _ = _run_cmd(["xdotool", "search", "--name", title_or_id, "windowclose"])
        return ok_xd


class SystemController:
    """Unified coordinator for all Linux system and hardware controllers."""

    def __init__(self):
        self.audio = AudioController()
        self.brightness = BrightnessController()
        self.bluetooth = BluetoothController()
        self.network = NetworkController()
        self.power = PowerController()
        self.process = ProcessController()


_GLOBAL_CONTROLLER: Optional[SystemController] = None


def get_system_controller() -> SystemController:
    global _GLOBAL_CONTROLLER
    if _GLOBAL_CONTROLLER is None:
        _GLOBAL_CONTROLLER = SystemController()
    return _GLOBAL_CONTROLLER
