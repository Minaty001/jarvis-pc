"""Local Subnet Discovery, ARP Inspector and IoT Device Classifier for JARVIS PC."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import logging
import re
import shutil
import socket
import subprocess  # nosec B404
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Common IoT device ports and service mappings
_IOT_PORT_SIGNATURES: Dict[int, str] = {
    80: "HTTP Web Server / Smart Device Portal",
    443: "HTTPS Web Server",
    554: "RTSP IP Camera Stream",
    1883: "MQTT Smart Home Broker",
    8008: "Google Cast / Chromecast",
    8009: "Google Cast Protocol",
    8080: "HTTP Alternate / Home Assistant / IP Camera",
    8123: "Home Assistant Web UI",
    8443: "HTTPS Alternate",
    9000: "Portainer / Docker / Media Server",
    9100: "RAW Network Printer (JetDirect)",
    50000: "UPnP / DLNA Media Renderer",
}

# Known OUI vendors for IoT identification
_MAC_OUI_VENDORS: Dict[str, str] = {
    "b8:27:eb": "Raspberry Pi Foundation",
    "dc:a6:32": "Raspberry Pi Foundation",
    "e4:5f:01": "Raspberry Pi Trading",
    "28:cd:c1": "Raspberry Pi Trading",
    "00:17:88": "Philips Hue Bridge",
    "ec:b5:fa": "Philips Lighting",
    "50:c7:bf": "TP-Link Smart Home (Kasa/Tapo)",
    "60:01:94": "Espressif Inc (ESP8266/ESP32 / WLED / Tasmota)",
    "24:62:ab": "Espressif Inc (ESP8266/ESP32 / Smart Plug)",
    "30:ae:a4": "Espressif Inc (ESP8266/ESP32)",
    "84:0d:8e": "Espressif Inc (ESP32 Smart Device)",
    "d8:a0:1d": "Tuya Smart Inc",
    "10:2c:6b": "Sonos Smart Audio",
    "00:0e:58": "Sonos Smart Audio",
    "f0:f0:02": "Google Nest / Chromecast",
    "54:60:09": "Google Nest",
    "ac:37:43": "Amazon Technologies (Echo / Fire TV)",
    "fc:65:de": "Amazon Technologies (Echo / Alexa)",
    "00:11:32": "Synology NAS Storage",
}


@dataclass
class NetworkDevice:
    """Represents a discovered local network device / IoT node."""
    ip: str
    mac: str = "Unknown"
    hostname: str = "Unknown"
    vendor: str = "Unknown"
    device_type: str = "Generic Network Device"
    open_ports: List[int] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    last_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_local_ip_and_gateway() -> tuple[str, str]:
    """Determine the primary local IPv4 address and default gateway."""
    local_ip = "127.0.0.1"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Connecting to a public IP doesn't actually transmit data over UDP, but determines routing interface
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
    except Exception:
        pass

    # Read default gateway from /proc/net/route
    gateway_ip = "Unknown"
    try:
        with open("/proc/net/route", "r") as f:
            for line in f.readlines()[1:]:
                fields = line.strip().split()
                if len(fields) >= 3 and fields[1] == "00000000":
                    gw_hex = fields[2]
                    if len(gw_hex) >= 8:
                        # Convert little-endian hex to IP
                        octets = [str(int(gw_hex[i:i+2], 16)) for i in (6, 4, 2, 0)]
                        gateway_ip = ".".join(octets)
                        break
    except Exception:
        pass

    return local_ip, gateway_ip


def parse_arp_table() -> Dict[str, str]:
    """Read kernel ARP cache (/proc/net/arp or `ip neigh`) mapping IP -> MAC."""
    ip_to_mac: Dict[str, str] = {}
    try:
        with open("/proc/net/arp", "r") as f:
            lines = f.readlines()[1:]
            for line in lines:
                parts = line.split()
                if len(parts) >= 4:
                    ip = parts[0].strip()
                    mac = parts[3].strip().lower()
                    if mac != "00:00:00:00:00:00" and len(mac) == 17:
                        ip_to_mac[ip] = mac
    except Exception as exc:
        logger.debug("Could not read /proc/net/arp: %s", exc)

    if not ip_to_mac:
        try:
            ip_bin = shutil.which("ip") or "/sbin/ip"
            res = subprocess.run([ip_bin, "neigh", "show"], capture_output=True, text=True, timeout=2.0, check=False)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 5 and "lladdr" in parts:
                        idx = parts.index("lladdr")
                        if idx + 1 < len(parts):
                            ip = parts[0]
                            mac = parts[idx + 1].lower()
                            if len(mac) == 17:
                                ip_to_mac[ip] = mac
        except Exception:
            pass

    return ip_to_mac


def identify_vendor_and_type(mac: str, open_ports: List[int]) -> tuple[str, str]:
    """Infer vendor and device category based on MAC OUI and open TCP ports."""
    mac_lower = mac.lower()
    prefix_3 = mac_lower[:8]
    vendor = _MAC_OUI_VENDORS.get(prefix_3, "Unknown Vendor")

    # Infer device type
    if 8123 in open_ports or 1883 in open_ports:
        dtype = "Smart Home Hub / Home Assistant"
    elif 8008 in open_ports or 8009 in open_ports or "Chromecast" in vendor or "Sonos" in vendor:
        dtype = "Smart Media Speaker / Cast Device"
    elif 554 in open_ports:
        dtype = "IP Security Camera (RTSP)"
    elif 9100 in open_ports:
        dtype = "Network Printer"
    elif "Raspberry Pi" in vendor:
        dtype = "Single Board Computer (Raspberry Pi)"
    elif "Espressif" in vendor or "Tuya" in vendor or "TP-Link" in vendor:
        dtype = "Smart IoT Microcontroller / Light / Plug"
    elif "Amazon" in vendor:
        dtype = "Amazon Echo Smart Speaker"
    elif 80 in open_ports or 443 in open_ports or 8080 in open_ports:
        dtype = "Web Server / Router / Gateway"
    else:
        dtype = "Connected Network Client"

    return vendor, dtype


def probe_ports(ip: str, ports: tuple[int, ...] = (80, 443, 554, 1883, 8008, 8080, 8123, 9100), timeout: float = 0.4) -> List[int]:
    """Check open TCP ports on target host."""
    open_ports: List[int] = []
    for port in ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                if sock.connect_ex((ip, port)) == 0:
                    open_ports.append(port)
        except Exception:
            pass
    return open_ports


def resolve_hostname(ip: str) -> str:
    """Resolve PTR record hostname with fast timeout."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return "Unknown"


async def scan_subnet(subnet_base: str = "", max_hosts: int = 30) -> List[NetworkDevice]:
    """Scan local subnet hosts via ARP and quick port sweeps."""
    local_ip, gateway = get_local_ip_and_gateway()

    if not subnet_base:
        if local_ip != "127.0.0.1":
            parts = local_ip.split(".")
            subnet_base = f"{parts[0]}.{parts[1]}.{parts[2]}"
        else:
            subnet_base = "192.168.1"

    arp_map = parse_arp_table()
    devices: List[NetworkDevice] = []

    # Include local host and gateway explicitly
    discovered_ips = set(arp_map.keys())
    if local_ip != "127.0.0.1":
        discovered_ips.add(local_ip)
    if gateway != "Unknown":
        discovered_ips.add(gateway)

    # Sort IPs for clean display
    def _ip_key(ip_str: str) -> tuple[int, ...]:
        try:
            return tuple(int(x) for x in ip_str.split("."))
        except Exception:
            return (0, 0, 0, 0)

    sorted_ips = sorted(list(discovered_ips), key=_ip_key)[:max_hosts]

    async def _inspect_host(ip: str) -> NetworkDevice:
        mac = arp_map.get(ip, "Local Interface" if ip == local_ip else "Unknown")
        hostname = await asyncio.to_thread(resolve_hostname, ip)
        open_ports = await asyncio.to_thread(probe_ports, ip)
        vendor, dtype = identify_vendor_and_type(mac, open_ports)
        services = [_IOT_PORT_SIGNATURES[p] for p in open_ports if p in _IOT_PORT_SIGNATURES]

        if ip == gateway:
            dtype = "Default Gateway / Network Router"

        return NetworkDevice(
            ip=ip,
            mac=mac,
            hostname=hostname,
            vendor=vendor,
            device_type=dtype,
            open_ports=open_ports,
            services=services,
        )

    tasks = [_inspect_host(ip) for ip in sorted_ips]
    if tasks:
        devices = await asyncio.gather(*tasks)

    return sorted(devices, key=lambda d: _ip_key(d.ip))
