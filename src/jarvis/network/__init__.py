"""Network Intelligence, IoT Discovery & Wake-on-LAN Package for JARVIS PC."""

from __future__ import annotations

from jarvis.network.hub import NetworkHub, get_network_hub
from jarvis.network.scanner import NetworkDevice, get_local_ip_and_gateway, parse_arp_table, scan_subnet
from jarvis.network.speed import benchmark_dns, benchmark_network, ping_host
from jarvis.network.wol import create_magic_packet, parse_mac_address, send_wake_on_lan

__all__ = [
    "NetworkHub",
    "get_network_hub",
    "NetworkDevice",
    "get_local_ip_and_gateway",
    "parse_arp_table",
    "scan_subnet",
    "benchmark_dns",
    "benchmark_network",
    "ping_host",
    "parse_mac_address",
    "create_magic_packet",
    "send_wake_on_lan",
]
