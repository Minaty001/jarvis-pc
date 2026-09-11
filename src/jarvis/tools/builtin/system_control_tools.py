"""Builtin agent tools for Linux hardware and system control."""

from __future__ import annotations

import logging
from typing import Optional

from jarvis.system.control import get_system_controller

logger = logging.getLogger(__name__)


def set_system_volume(level: int, mute: Optional[bool] = None) -> str:
    """Set system audio volume (0-100%) and optional mute state."""
    ctrl = get_system_controller()
    if mute is not None:
        ctrl.audio.set_mute(mute)
    ok = ctrl.audio.set_volume(level)
    info = ctrl.audio.get_volume()
    mute_str = " (MUTED)" if info.get("muted") else ""
    return f"System volume set to {info.get('percent', level)}%{mute_str}."


def get_system_volume() -> str:
    """Query current audio volume percentage and mute status."""
    ctrl = get_system_controller()
    info = ctrl.audio.get_volume()
    status = "MUTED" if info.get("muted") else "ACTIVE"
    return f"Current audio volume: {info.get('percent')}% [{status}] (backend: {info.get('backend')})."


def set_display_brightness(level: int) -> str:
    """Set screen display brightness (5-100%)."""
    ctrl = get_system_controller()
    ok = ctrl.brightness.set_brightness(level)
    info = ctrl.brightness.get_brightness()
    return f"Display brightness set to {info.get('percent', level)}%."


def get_display_brightness() -> str:
    """Query current screen brightness percentage."""
    ctrl = get_system_controller()
    info = ctrl.brightness.get_brightness()
    return f"Current display brightness: {info.get('percent')}% (backend: {info.get('backend')})."


def manage_bluetooth(action: str, device: Optional[str] = None) -> str:
    """Manage Bluetooth adapter and devices (actions: list, on, off, connect, disconnect)."""
    ctrl = get_system_controller()
    act = action.strip().lower()

    if act == "list":
        devs = ctrl.bluetooth.list_devices()
        if not devs:
            return "No paired or available Bluetooth devices found."
        lines = [f"Discovered {len(devs)} Bluetooth Device(s):"]
        for d in devs:
            lines.append(f"• {d['mac']} | {d['name']}")
        return "\n".join(lines)

    elif act == "on":
        ctrl.bluetooth.set_power(True)
        return "Bluetooth adapter powered ON."

    elif act == "off":
        ctrl.bluetooth.set_power(False)
        return "Bluetooth adapter powered OFF."

    elif act == "connect":
        if not device:
            return "Error: Device name or MAC address required for connect."
        ok = ctrl.bluetooth.connect_device(device)
        return f"Bluetooth connect to '{device}': {'success' if ok else 'failed (device not in range)'}."

    elif act == "disconnect":
        if not device:
            return "Error: Device name or MAC address required for disconnect."
        ok = ctrl.bluetooth.disconnect_device(device)
        return f"Bluetooth disconnect from '{device}': {'success' if ok else 'failed'}."

    return f"Unknown Bluetooth action '{action}'. Supported: list, on, off, connect, disconnect."


def manage_network(action: str) -> str:
    """Monitor network connections and Wi-Fi state (actions: status, list_wifi, wifi_on, wifi_off)."""
    ctrl = get_system_controller()
    act = action.strip().lower()

    if act == "status":
        info = ctrl.network.get_status()
        conn_str = "CONNECTED" if info["connected"] else "DISCONNECTED"
        return (
            f"Network Status: {conn_str}\n"
            f"• Active SSID / Net: {info['ssid']}\n"
            f"• IP Address:       {info['ip']}\n"
            f"• Interface:        {info['interface']}"
        )

    elif act in ("list_wifi", "scan", "wifi_list"):
        wifis = ctrl.network.list_wifi()
        if not wifis:
            return "No Wi-Fi access points detected."
        lines = [f"Discovered {len(wifis)} Wi-Fi Access Point(s):"]
        for w in wifis[:10]:
            lines.append(f"• {w['ssid']:<22} | Signal: {w['signal']}% | {w['security']}")
        return "\n".join(lines)

    elif act == "wifi_on":
        ctrl.network.set_wifi_power(True)
        return "Wi-Fi radio enabled."

    elif act == "wifi_off":
        ctrl.network.set_wifi_power(False)
        return "Wi-Fi radio disabled."

    return f"Unknown network action '{action}'. Supported: status, list_wifi, wifi_on, wifi_off."


def manage_power(action: str) -> str:
    """Manage workstation power state (actions: lock, suspend, reboot, shutdown). Requires confirmation."""
    ctrl = get_system_controller()
    act = action.strip().lower()

    if act == "lock":
        ok = ctrl.power.lock_session()
        return "Workstation desktop session locked." if ok else "Failed to lock session."

    elif act == "suspend":
        ctrl.power.suspend()
        return "System suspend initiated."

    elif act == "reboot":
        ctrl.power.reboot()
        return "System reboot initiated."

    elif act in ("shutdown", "poweroff"):
        ctrl.power.poweroff()
        return "System poweroff initiated."

    return f"Unknown power action '{action}'. Supported: lock, suspend, reboot, shutdown."


def manage_process(action: str, target: str, force: bool = False) -> str:
    """Manage application processes and windows (actions: kill, close_window)."""
    ctrl = get_system_controller()
    act = action.strip().lower()

    if act == "kill":
        res = ctrl.process.kill_process(target, force=force)
        if res["success"]:
            return f"Terminated {res['killed']} process(es) matching '{target}' (PIDs: {res['pids']})."
        return f"No running processes found matching '{target}'."

    elif act in ("close_window", "close"):
        ok = ctrl.process.close_window(target)
        return f"Close window '{target}': {'success' if ok else 'failed (window not found)'}."

    return f"Unknown process action '{action}'. Supported: kill, close_window."
