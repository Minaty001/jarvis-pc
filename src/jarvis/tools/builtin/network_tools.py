"""Builtin agent tools for Network Diagnostics, IoT Device Scanning & Wake-on-LAN."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from jarvis.cognitive.context import ExecutionContext
from jarvis.network.hub import get_network_hub


async def scan_local_network(subnet: str = "") -> str:
    """Scan local subnet for connected computers, smartphones, smart home IoT nodes, cameras, and printers."""
    hub = get_network_hub()
    devices = await hub.scan_network(subnet_base=subnet)
    if not devices:
        return "No network devices discovered on the local subnet."

    lines = [f"JARVIS Local Network Scan ({len(devices)} devices found):"]
    lines.append("=" * 75)
    lines.append(f"{'IP ADDRESS':<16} | {'MAC ADDRESS':<18} | {'DEVICE TYPE / VENDOR':<24} | {'OPEN PORTS'}")
    lines.append("-" * 75)
    for d in devices:
        ports_str = ",".join(str(p) for p in d.open_ports) if d.open_ports else "none"
        type_str = f"{d.device_type} ({d.vendor})" if d.vendor != "Unknown Vendor" else d.device_type
        if len(type_str) > 24:
            type_str = type_str[:21] + "..."
        lines.append(f"{d.ip:<16} | {d.mac:<18} | {type_str:<24} | {ports_str}")
    lines.append("=" * 75)

    return "\n".join(lines)


async def wake_on_lan(mac_address: str, broadcast_ip: str = "255.255.255.255") -> str:
    """Send a Wake-on-LAN magic packet to remotely power on a target workstation or server by MAC address."""
    hub = get_network_hub()
    success = hub.wake_on_lan(mac_address=mac_address, broadcast_ip=broadcast_ip)
    if success:
        return f"Wake-on-LAN magic packet successfully transmitted to MAC {mac_address} via broadcast {broadcast_ip}."
    return f"Failed to send Wake-on-LAN packet to MAC {mac_address}."


async def ping_network_host(host: str, count: int = 3) -> str:
    """Ping a host, server, or local IP address to test connectivity, latency, jitter, and packet loss."""
    hub = get_network_hub()
    res = await asyncio.to_thread(hub.ping, host=host, count=count)
    if not res["reachable"]:
        return f"Host '{host}' is UNREACHABLE (100% packet loss)."

    return (
        f"Ping results for {res['host']}:\n"
        f"• Status:      ONLINE\n"
        f"• Avg Latency: {res['avg_ms']} ms (min: {res['min_ms']} ms, max: {res['max_ms']} ms)\n"
        f"• Jitter:      {res['jitter_ms']} ms\n"
        f"• Packet Loss: {res['packet_loss_percent']}%"
    )


async def benchmark_network_speed() -> str:
    """Run a complete network diagnostic benchmark (WAN ping, DNS latency, HTTP check, quality grade)."""
    hub = get_network_hub()
    bench = await hub.benchmark()
    status_str = "ONLINE" if bench["online"] else "OFFLINE"

    lines = [
        "JARVIS Network Benchmark & Quality Diagnostics:",
        "=" * 55,
        f"• Connectivity:   {status_str}",
        f"• Quality Grade:  {bench['quality_score']}",
        f"• Avg Latency:    {bench['avg_latency_ms']} ms",
        f"• Jitter:         {bench['jitter_ms']} ms",
        f"• Packet Loss:    {bench['packet_loss_percent']}%",
        f"• DNS Resolution: {bench['dns_lookup_ms']} ms ({bench['dns_status']})",
    ]
    if bench.get("http_rtt_ms") is not None:
        lines.append(f"• HTTP Roundtrip: {bench['http_rtt_ms']} ms")
    lines.append("=" * 55)

    return "\n".join(lines)


async def list_network_devices() -> str:
    """List previously discovered and cached local network devices from the registry."""
    hub = get_network_hub()
    devices = hub.list_devices()
    if not devices:
        return "No network devices in local registry cache. Run scan_local_network first."

    lines = [f"Cached Local Network Devices ({len(devices)} records):"]
    lines.append("=" * 75)
    for d in devices:
        lines.append(f"• {d.ip:<15} [{d.mac}] | {d.device_type} ({d.vendor}) | Hostname: {d.hostname}")
    lines.append("=" * 75)

    return "\n".join(lines)
