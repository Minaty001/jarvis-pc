"""Network and IoT Intelligence Hub for JARVIS PC."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.network.scanner import NetworkDevice, scan_subnet
from jarvis.network.speed import benchmark_network, ping_host
from jarvis.network.wol import send_wake_on_lan
from jarvis.system.paths import get_app_paths

logger = logging.getLogger(__name__)

_DEFAULT_STORE_PATH = get_app_paths().state / "network_devices.json"
_NETWORK_HUB_SINGLETON: Optional[NetworkHub] = None


class NetworkHub:
    """Central manager for LAN discovery, IoT device mapping, latency benchmarks, and Wake-on-LAN."""

    def __init__(self, store_path: Optional[Path | str] = None) -> None:
        self.store_path = Path(store_path) if store_path else _DEFAULT_STORE_PATH
        self._devices: Dict[str, NetworkDevice] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if self.store_path.exists():
            try:
                data = json.loads(self.store_path.read_text(encoding="utf-8"))
                for item in data:
                    dev = NetworkDevice(**item)
                    self._devices[dev.ip] = dev
            except Exception as exc:
                logger.debug("Could not load network cache from %s: %s", self.store_path, exc)

    def _save_cache(self) -> None:
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            data = [d.to_dict() for d in self._devices.values()]
            self.store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.debug("Could not save network cache: %s", exc)

    async def scan_network(self, subnet_base: str = "", max_hosts: int = 30) -> List[NetworkDevice]:
        """Scan local subnet, discover IoT devices, and persist to registry."""
        devices = await scan_subnet(subnet_base=subnet_base, max_hosts=max_hosts)
        for d in devices:
            self._devices[d.ip] = d
        self._save_cache()
        return devices

    def list_devices(self) -> List[NetworkDevice]:
        """Return all known devices from registry."""
        return list(self._devices.values())

    def ping(self, host: str, count: int = 3) -> Dict[str, Any]:
        """Ping a remote host or local device."""
        return ping_host(host=host, count=count)

    def wake_on_lan(self, mac_address: str, broadcast_ip: str = "255.255.255.255") -> bool:
        """Transmit a Wake-on-LAN packet."""
        return send_wake_on_lan(mac_address=mac_address, broadcast_ip=broadcast_ip)

    async def benchmark(self) -> Dict[str, Any]:
        """Execute a full network diagnostic and speed benchmark."""
        return await benchmark_network()


def get_network_hub() -> NetworkHub:
    """Get or create singleton instance of NetworkHub."""
    global _NETWORK_HUB_SINGLETON
    if _NETWORK_HUB_SINGLETON is None:
        _NETWORK_HUB_SINGLETON = NetworkHub()
    return _NETWORK_HUB_SINGLETON
