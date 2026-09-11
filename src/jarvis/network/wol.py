"""Wake-on-LAN (WoL) Magic Packet Generator and Dispatcher for JARVIS PC."""

from __future__ import annotations

import logging
import re
import socket
from typing import Optional

logger = logging.getLogger(__name__)


def parse_mac_address(mac_str: str) -> bytes:
    """Normalize and parse a MAC address string into 6 raw bytes.

    Supports formats like:
    - 00:11:22:33:44:55
    - 00-11-22-33-44-55
    - 0011.2233.4455
    - 001122334455
    """
    clean = re.sub(r"[^0-9a-fA-F]", "", mac_str)
    if len(clean) != 12:
        raise ValueError(f"Invalid MAC address format: '{mac_str}'. Expected 12 hexadecimal characters.")
    return bytes.fromhex(clean)


def create_magic_packet(mac_bytes: bytes) -> bytes:
    """Build a standard Wake-on-LAN magic packet (6 bytes of 0xFF followed by 16 repetitions of the target MAC)."""
    if len(mac_bytes) != 6:
        raise ValueError(f"MAC address must be exactly 6 bytes, got {len(mac_bytes)}")
    return (b"\xff" * 6) + (mac_bytes * 16)


def send_wake_on_lan(
    mac_address: str,
    broadcast_ip: str = "255.255.255.255",
    port: int = 9,
) -> bool:
    """Send a Wake-on-LAN magic packet to power on a remote machine.

    Args:
        mac_address: Target network interface MAC address.
        broadcast_ip: Destination broadcast address (default: 255.255.255.255).
        port: Destination UDP port (default: 9, alternate: 7).

    Returns:
        True if the packet was sent successfully, False otherwise.
    """
    try:
        mac_bytes = parse_mac_address(mac_address)
        packet = create_magic_packet(mac_bytes)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(packet, (broadcast_ip, port))

        logger.info("Wake-on-LAN packet dispatched to %s via %s:%d", mac_address, broadcast_ip, port)
        return True
    except Exception as exc:
        logger.error("Failed to send Wake-on-LAN packet to '%s': %s", mac_address, exc)
        return False
