"""System Info — CPU, memory, disk, network, time, battery."""

import datetime
import platform
from typing import Any

from config.logger import get_logger

logger = get_logger("tools.system_info")

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def get_time() -> dict[str, Any]:
    now = datetime.datetime.now()
    return {"success": True, "result": now.strftime("%I:%M %p"), "time": now.isoformat()}


def get_date() -> dict[str, Any]:
    now = datetime.datetime.now()
    return {"success": True, "result": now.strftime("%A, %B %d, %Y"), "date": now.date().isoformat()}


def get_battery() -> dict[str, Any]:
    if not HAS_PSUTIL:
        return {"success": False, "result": "psutil not installed"}
    bat = psutil.sensors_battery()
    if bat is None:
        return {"success": True, "result": "No battery detected (desktop system)"}
    return {
        "success": True,
        "result": f"Battery: {bat.percent}% {'(charging)' if bat.power_plugged else '(on battery)'}",
        "percent": bat.percent,
        "plugged": bat.power_plugged,
    }


def get_cpu() -> dict[str, Any]:
    if not HAS_PSUTIL:
        return {"success": False, "result": "psutil not installed"}
    usage = psutil.cpu_percent(interval=1)
    freq = psutil.cpu_freq()
    cores = psutil.cpu_count()
    return {
        "success": True,
        "result": f"CPU: {usage}% ({cores} cores)",
        "percent": usage,
        "cores": cores,
        "freq_mhz": freq.current if freq else None,
    }


def get_memory() -> dict[str, Any]:
    if not HAS_PSUTIL:
        return {"success": False, "result": "psutil not installed"}
    mem = psutil.virtual_memory()
    return {
        "success": True,
        "result": f"RAM: {mem.percent}% ({mem.used // (1024**3):.1f}GB / {mem.total // (1024**3):.1f}GB)",
        "percent": mem.percent,
        "used_gb": round(mem.used / (1024**3), 1),
        "total_gb": round(mem.total / (1024**3), 1),
    }


def get_disk() -> dict[str, Any]:
    if not HAS_PSUTIL:
        return {"success": False, "result": "psutil not installed"}
    disk = psutil.disk_usage("/")
    return {
        "success": True,
        "result": f"Disk: {disk.percent}% ({disk.used // (1024**3):.1f}GB / {disk.total // (1024**3):.1f}GB)",
        "percent": disk.percent,
        "used_gb": round(disk.used / (1024**3), 1),
        "total_gb": round(disk.total / (1024**3), 1),
    }


def get_network() -> dict[str, Any]:
    if not HAS_PSUTIL:
        return {"success": False, "result": "psutil not installed"}
    addrs = psutil.net_if_addrs()
    net_io = psutil.net_io_counters()
    ips = []
    for iface, addr_list in addrs.items():
        for addr in addr_list:
            if addr.family.name == "AF_INET" and not addr.address.startswith("127."):
                ips.append(f"{iface}: {addr.address}")
    return {
        "success": True,
        "result": f"Network: {', '.join(ips) if ips else 'No connection'} | Sent: {net_io.bytes_sent // (1024**2):.1f}MB, Recv: {net_io.bytes_recv // (1024**2):.1f}MB",
        "ips": ips,
    }
