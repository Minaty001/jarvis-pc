"""Tests for Linux System & Hardware Control Hub (Audio, Brightness, Bluetooth, Network, Power, Process)."""

from unittest.mock import MagicMock, patch
import pytest

from jarvis.cli.main import run_cli
from jarvis.system.control import (
    AudioController,
    BrightnessController,
    BluetoothController,
    NetworkController,
    PowerController,
    ProcessController,
    SystemController,
    get_system_controller,
)
from jarvis.tools.builtin.system_control_tools import (
    get_display_brightness,
    get_system_volume,
    manage_bluetooth,
    manage_network,
    manage_power,
    manage_process,
    set_display_brightness,
    set_system_volume,
)


# ==========================================
# AudioController Tests
# ==========================================

def test_audio_controller_set_and_get_volume_pactl():
    ctrl = AudioController()
    with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd == "pactl" else None
        
        # Test set volume
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert ctrl.set_volume(75) is True
        mock_run.assert_called_with(["/usr/bin/pactl", "set-sink-volume", "@DEFAULT_SINK@", "75%"], capture_output=True, text=True, timeout=8.0, check=False)

        # Test set mute
        assert ctrl.set_mute(True) is True
        mock_run.assert_called_with(["/usr/bin/pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"], capture_output=True, text=True, timeout=8.0, check=False)

        # Test get volume
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Sink #0\n\tMute: no\n\tVolume: front-left: 49152 /  75% / -7.50 dB,   front-right: 49152 /  75% / -7.50 dB\n",
            stderr="",
        )
        info = ctrl.get_volume()
        assert info["percent"] == 75
        assert info["muted"] is False
        assert info["backend"] == "pactl"


def test_audio_controller_clamping():
    ctrl = AudioController()
    with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
        mock_which.return_value = "/usr/bin/pactl"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        # Clamping above 100
        ctrl.set_volume(150)
        mock_run.assert_called_with(["/usr/bin/pactl", "set-sink-volume", "@DEFAULT_SINK@", "100%"], capture_output=True, text=True, timeout=8.0, check=False)

        # Clamping below 0
        ctrl.set_volume(-20)
        mock_run.assert_called_with(["/usr/bin/pactl", "set-sink-volume", "@DEFAULT_SINK@", "0%"], capture_output=True, text=True, timeout=8.0, check=False)


# ==========================================
# BrightnessController Tests
# ==========================================

def test_brightness_controller_brightnessctl():
    ctrl = BrightnessController()
    with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd == "brightnessctl" else None

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert ctrl.set_brightness(60) is True
        mock_run.assert_called_with(["/usr/bin/brightnessctl", "set", "60%"], capture_output=True, text=True, timeout=8.0, check=False)

        # brightnessctl -m format: device,class,curr,curr%,max
        mock_run.return_value = MagicMock(returncode=0, stdout="intel_backlight,backlight,600,60%,1000\n", stderr="")
        info = ctrl.get_brightness()
        assert info["percent"] == 60
        assert info["backend"] == "brightnessctl"


def test_brightness_controller_clamping():
    ctrl = BrightnessController()
    with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
        mock_which.return_value = "/usr/bin/brightnessctl"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Minimum clamp is 5% to avoid screen blackout
        ctrl.set_brightness(1)
        mock_run.assert_called_with(["/usr/bin/brightnessctl", "set", "5%"], capture_output=True, text=True, timeout=8.0, check=False)


# ==========================================
# BluetoothController Tests
# ==========================================

def test_bluetooth_controller():
    ctrl = BluetoothController()
    with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
        mock_which.return_value = "/usr/bin/bluetoothctl"

        # List devices
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Device 00:11:22:33:44:55 Sony WH-1000XM4\nDevice AA:BB:CC:DD:EE:FF Wireless Mouse\n",
            stderr="",
        )
        devs = ctrl.list_devices()
        assert len(devs) == 2
        assert devs[0]["mac"] == "00:11:22:33:44:55"
        assert devs[0]["name"] == "Sony WH-1000XM4"

        # Power on
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert ctrl.set_power(True) is True
        mock_run.assert_called_with(["/usr/bin/bluetoothctl", "power", "on"], capture_output=True, text=True, timeout=8.0, check=False)

        # Connect
        assert ctrl.connect_device("00:11:22:33:44:55") is True
        mock_run.assert_called_with(["/usr/bin/bluetoothctl", "connect", "00:11:22:33:44:55"], capture_output=True, text=True, timeout=8.0, check=False)


# ==========================================
# NetworkController Tests
# ==========================================

def test_network_controller():
    ctrl = NetworkController()
    with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run, patch("psutil.net_if_addrs") as mock_addrs:
        mock_which.return_value = "/usr/bin/nmcli"
        
        # Status
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="yes:Home-5G:wlan0\nno:OtherNet:wlan0\n",
            stderr="",
        )
        # Mock psutil addresses
        addr = MagicMock()
        addr.family.name = "AF_INET"
        addr.address = "192.168.1.105"
        mock_addrs.return_value = {"wlan0": [addr]}

        status = ctrl.get_status()
        assert status["connected"] is True
        assert status["ssid"] == "Home-5G"
        assert status["interface"] == "wlan0"
        assert status["ip"] == "192.168.1.105"

        # List wifi
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Home-5G:85:WPA2\nOffice-WiFi:60:WPA2\n",
            stderr="",
        )
        wifis = ctrl.list_wifi()
        assert len(wifis) >= 1
        assert wifis[0]["ssid"] == "Home-5G"
        assert wifis[0]["signal"] == "85"

        # Wifi power
        assert ctrl.set_wifi_power(False) is True
        mock_run.assert_called_with(["/usr/bin/nmcli", "radio", "wifi", "off"], capture_output=True, text=True, timeout=8.0, check=False)


# ==========================================
# PowerController Tests
# ==========================================

def test_power_controller():
    ctrl = PowerController()
    with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        assert ctrl.lock_session() is True
        mock_run.assert_called_with(["/usr/bin/loginctl", "lock-session"], capture_output=True, text=True, timeout=8.0, check=False)

        assert ctrl.suspend() is True
        mock_run.assert_called_with(["/usr/bin/systemctl", "suspend"], capture_output=True, text=True, timeout=8.0, check=False)

        assert ctrl.reboot() is True
        mock_run.assert_called_with(["/usr/bin/systemctl", "reboot"], capture_output=True, text=True, timeout=8.0, check=False)

        assert ctrl.poweroff() is True
        mock_run.assert_called_with(["/usr/bin/systemctl", "poweroff"], capture_output=True, text=True, timeout=8.0, check=False)


# ==========================================
# ProcessController Tests
# ==========================================

def test_process_controller():
    ctrl = ProcessController()
    with patch("psutil.process_iter") as mock_iter:
        p1 = MagicMock()
        p1.info = {"pid": 12345, "name": "firefox", "cmdline": ["/usr/lib/firefox/firefox"]}
        mock_iter.return_value = [p1]

        res = ctrl.kill_process("firefox", force=False)
        assert res["success"] is True
        assert res["killed"] == 1
        assert 12345 in res["pids"]
        p1.terminate.assert_called_once()

    # Window close
    with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd == "wmctrl" else None
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert ctrl.close_window("Terminal") is True
        mock_run.assert_called_with(["/usr/bin/wmctrl", "-c", "Terminal"], capture_output=True, text=True, timeout=8.0, check=False)


# ==========================================
# Unified SystemController & Tools Tests
# ==========================================

def test_system_controller_singleton():
    c1 = get_system_controller()
    c2 = get_system_controller()
    assert c1 is c2
    assert isinstance(c1, SystemController)


def test_builtin_system_tools():
    with patch("jarvis.system.control.AudioController.set_volume", return_value=True), \
         patch("jarvis.system.control.AudioController.get_volume", return_value={"percent": 50, "muted": False, "backend": "pactl"}):
        res = set_system_volume(50)
        assert "50%" in res
        info = get_system_volume()
        assert "50%" in info

    with patch("jarvis.system.control.BrightnessController.set_brightness", return_value=True), \
         patch("jarvis.system.control.BrightnessController.get_brightness", return_value={"percent": 80, "backend": "brightnessctl"}):
        res = set_display_brightness(80)
        assert "80%" in res
        info = get_display_brightness()
        assert "80%" in info

    with patch("jarvis.system.control.BluetoothController.list_devices", return_value=[{"mac": "11:22:33:44:55:66", "name": "Headphones"}]):
        res = manage_bluetooth("list")
        assert "Headphones" in res

    with patch("jarvis.system.control.NetworkController.get_status", return_value={"connected": True, "ssid": "MyWiFi", "ip": "192.168.1.50", "interface": "wlan0"}):
        res = manage_network("status")
        assert "MyWiFi" in res
        assert "192.168.1.50" in res

    with patch("jarvis.system.control.PowerController.lock_session", return_value=True):
        res = manage_power("lock")
        assert "locked" in res

    with patch("jarvis.system.control.ProcessController.kill_process", return_value={"success": True, "killed": 1, "pids": [9999]}):
        res = manage_process("kill", "test_app")
        assert "Terminated 1 process(es)" in res


# ==========================================
# CLI Execution Tests
# ==========================================

def test_cli_control_subcommands(capsys):
    with patch("jarvis.system.control.AudioController.set_volume", return_value=True), \
         patch("jarvis.system.control.AudioController.get_volume", return_value={"percent": 42, "muted": False, "backend": "pactl"}):
        ret = run_cli(["control", "volume", "42"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "42%" in captured.out

    with patch("jarvis.system.control.BrightnessController.set_brightness", return_value=True), \
         patch("jarvis.system.control.BrightnessController.get_brightness", return_value={"percent": 75, "backend": "brightnessctl"}):
        ret = run_cli(["control", "brightness", "75"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "75%" in captured.out

    with patch("jarvis.system.control.BluetoothController.set_power", return_value=True):
        ret = run_cli(["control", "bluetooth", "on"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "powered ON" in captured.out

    with patch("jarvis.system.control.NetworkController.get_status", return_value={"connected": True, "ssid": "Home-5G", "ip": "192.168.1.100", "interface": "wlan0"}):
        ret = run_cli(["control", "wifi", "status"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Home-5G" in captured.out

    with patch("jarvis.system.control.PowerController.lock_session", return_value=True):
        ret = run_cli(["control", "power", "lock"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Session locked" in captured.out

    with patch("jarvis.system.control.ProcessController.kill_process", return_value={"success": True, "killed": 1, "pids": [1000]}):
        ret = run_cli(["control", "kill", "bad_process"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Terminated 1 process" in captured.out
