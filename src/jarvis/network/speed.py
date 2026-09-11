"""Network Latency, Jitter, DNS Resolution and Speed Benchmarking for JARVIS PC."""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess  # nosec B404
import time
from typing import Any, Dict, List, Optional
import urllib.request

logger = logging.getLogger(__name__)


def ping_host(host: str, count: int = 3, timeout_sec: float = 4.0) -> Dict[str, Any]:
    """Execute ICMP ping against a target host and parse packet statistics.

    Returns dict with reachable status, packet loss, min/avg/max/mdev latencies.
    """
    clean_host = host.strip()
    ping_bin = shutil.which("ping") or "/bin/ping"

    try:
        res = subprocess.run(  # nosec B603
            [ping_bin, "-c", str(count), "-W", str(int(timeout_sec)), clean_host],
            capture_output=True,
            text=True,
            timeout=timeout_sec + 2.0,
            check=False,
        )

        stdout = res.stdout
        is_reachable = res.returncode == 0

        # Parse packet loss: "3 packets transmitted, 3 received, 0% packet loss"
        loss_match = re.search(r"(\d+)%\s+packet\s+loss", stdout)
        loss_percent = int(loss_match.group(1)) if loss_match else (0 if is_reachable else 100)

        # Parse RTT stats: "rtt min/avg/max/mdev = 12.345/14.567/16.789/1.234 ms"
        rtt_match = re.search(r"(?:rtt|round-trip)\s+min/avg/max/(?:mdev|stddev)\s*=\s*([0-9.]+)/([0-9.]+)/([0-9.]+)/([0-9.]+)\s*ms", stdout)
        if rtt_match:
            min_rtt = float(rtt_match.group(1))
            avg_rtt = float(rtt_match.group(2))
            max_rtt = float(rtt_match.group(3))
            jitter = float(rtt_match.group(4))
        else:
            min_rtt = avg_rtt = max_rtt = jitter = 0.0

        return {
            "host": clean_host,
            "reachable": is_reachable,
            "packet_loss_percent": loss_percent,
            "min_ms": round(min_rtt, 2),
            "avg_ms": round(avg_rtt, 2),
            "max_ms": round(max_rtt, 2),
            "jitter_ms": round(jitter, 2),
            "raw_output": stdout.strip(),
        }
    except Exception as exc:
        logger.debug("Ping error for %s: %s", clean_host, exc)
        return {
            "host": clean_host,
            "reachable": False,
            "packet_loss_percent": 100,
            "min_ms": 0.0,
            "avg_ms": 0.0,
            "max_ms": 0.0,
            "jitter_ms": 0.0,
            "error": str(exc),
        }


def benchmark_dns(domain: str = "cloudflare.com") -> Dict[str, Any]:
    """Measure DNS resolution lookup latency."""
    import socket
    start = time.perf_counter()
    try:
        ip = socket.gethostbyname(domain)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "domain": domain,
            "resolved_ip": ip,
            "lookup_ms": round(elapsed_ms, 2),
            "success": True,
        }
    except Exception as exc:
        return {
            "domain": domain,
            "resolved_ip": None,
            "lookup_ms": 0.0,
            "success": False,
            "error": str(exc),
        }


async def benchmark_network() -> Dict[str, Any]:
    """Run comprehensive network diagnostic benchmark (DNS, Gateway/WAN Ping, HTTP Latency)."""
    # 1. DNS Benchmark
    dns_res = benchmark_dns("1.1.1.1.nip.io" if False else "google.com")

    # 2. WAN Pings
    ping_cf = await asyncio.to_thread(ping_host, "1.1.1.1", count=3)
    ping_google = await asyncio.to_thread(ping_host, "8.8.8.8", count=3)

    # 3. HTTP Latency check
    http_start = time.perf_counter()
    http_ok = False
    http_ms = 0.0
    try:
        req = urllib.request.Request(
            "http://connectivitycheck.gstatic.com/generate_204",
            headers={"User-Agent": "JARVIS-Network-Bench/1.0"},
        )
        with urllib.request.urlopen(req, timeout=4.0) as resp:  # nosec B310
            if resp.status in (200, 204):
                http_ok = True
                http_ms = (time.perf_counter() - http_start) * 1000.0
    except Exception:
        pass

    primary_ping = ping_cf if ping_cf["reachable"] else ping_google

    return {
        "online": primary_ping["reachable"] or http_ok,
        "dns_lookup_ms": dns_res.get("lookup_ms", 0.0),
        "avg_latency_ms": primary_ping.get("avg_ms", 0.0),
        "jitter_ms": primary_ping.get("jitter_ms", 0.0),
        "packet_loss_percent": primary_ping.get("packet_loss_percent", 100),
        "http_rtt_ms": round(http_ms, 2) if http_ok else None,
        "dns_status": "optimal" if dns_res["success"] and dns_res["lookup_ms"] < 50 else "functional",
        "quality_score": (
            "EXCELLENT" if primary_ping.get("avg_ms", 999) < 25 and primary_ping.get("packet_loss_percent", 100) == 0
            else "GOOD" if primary_ping.get("avg_ms", 999) < 70 and primary_ping.get("packet_loss_percent", 100) <= 5
            else "FAIR" if primary_ping["reachable"]
            else "OFFLINE"
        ),
    }
