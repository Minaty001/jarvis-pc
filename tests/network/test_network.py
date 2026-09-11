"""Tests for Network Diagnostics, Local IoT Scanner, Wake-on-LAN and Speed Hub."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from jarvis.network.hub import NetworkHub
from jarvis.network.scanner import (
    NetworkDevice,
    get_local_ip_and_gateway,
    identify_vendor_and_type,
    parse_arp_table,
    scan_subnet,
)
from jarvis.network.speed import benchmark_dns, benchmark_network, ping_host
from jarvis.network.wol import create_magic_packet, parse_mac_address, send_wake_on_lan
from jarvis.tools.builtin.network_tools import (
    benchmark_network_speed,
    list_network_devices,
    ping_network_host,
    scan_local_network,
    wake_on_lan,
)


def test_parse_mac_address_and_magic_packet():
    # Valid formats
    mac1 = parse_mac_address("00:11:22:33:44:55")
    mac2 = parse_mac_address("00-11-22-33-44-55")
    mac3 = parse_mac_address("0011.2233.4455")
    mac4 = parse_mac_address("001122334455")

    expected = bytes.fromhex("001122334455")
    assert mac1 == mac2 == mac3 == mac4 == expected

    # Magic packet check
    packet = create_magic_packet(mac1)
    assert len(packet) == 102
    assert packet[:6] == b"\xff" * 6
    assert packet[6:12] == expected
    assert packet[-6:] == expected

    # Invalid MAC
    with pytest.raises(ValueError):
        parse_mac_address("invalid-mac")


def test_send_wake_on_lan_mocked():
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__.return_value = mock_sock

        ok = send_wake_on_lan("00:11:22:33:44:55", broadcast_ip="192.168.1.255", port=9)
        assert ok is True
        mock_sock.sendto.assert_called_once()
        args, _ = mock_sock.sendto.call_args
        assert len(args[0]) == 102
        assert args[1] == ("192.168.1.255", 9)


def test_ping_host_parsing():
    sample_ping_output = """
PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=1 ttl=58 time=12.4 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=58 time=14.8 ms
64 bytes from 1.1.1.1: icmp_seq=3 ttl=58 time=16.2 ms

--- 1.1.1.1 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 12.400/14.466/16.200/1.564 ms
"""
    with patch("subprocess.run") as mock_run:
        res_mock = MagicMock()
        res_mock.returncode = 0
        res_mock.stdout = sample_ping_output
        mock_run.return_value = res_mock

        res = ping_host("1.1.1.1")
        assert res["reachable"] is True
        assert res["packet_loss_percent"] == 0
        assert res["min_ms"] == 12.4
        assert res["avg_ms"] == 14.47
        assert res["max_ms"] == 16.2
        assert res["jitter_ms"] == 1.56


@pytest.mark.asyncio
async def test_benchmark_dns_and_network():
    with patch("socket.gethostbyname", return_value="1.1.1.1"):
        dns_res = benchmark_dns("cloudflare.com")
        assert dns_res["success"] is True
        assert dns_res["resolved_ip"] == "1.1.1.1"

    with patch("jarvis.network.speed.ping_host") as mock_ping, \
         patch("jarvis.network.speed.benchmark_dns") as mock_dns, \
         patch("urllib.request.urlopen") as mock_urlopen:

        mock_ping.return_value = {
            "reachable": True,
            "avg_ms": 15.0,
            "jitter_ms": 1.2,
            "packet_loss_percent": 0,
        }
        mock_dns.return_value = {
            "success": True,
            "lookup_ms": 12.0,
            "domain": "google.com",
        }
        mock_urlopen.return_value.__enter__.return_value.status = 204

        bench = await benchmark_network()
        assert bench["online"] is True
        assert bench["quality_score"] == "EXCELLENT"
        assert bench["avg_latency_ms"] == 15.0


def test_scanner_vendor_and_port_identification():
    # Raspberry Pi
    vendor, dtype = identify_vendor_and_type("dc:a6:32:11:22:33", open_ports=[])
    assert "Raspberry Pi" in vendor
    assert "Raspberry Pi" in dtype

    # Philips Hue
    vendor, dtype = identify_vendor_and_type("00:17:88:ab:cd:ef", open_ports=[80])
    assert "Philips" in vendor

    # Home Assistant
    vendor, dtype = identify_vendor_and_type("00:00:00:00:00:00", open_ports=[8123])
    assert "Home Assistant" in dtype

    # RTSP Camera
    vendor, dtype = identify_vendor_and_type("00:00:00:00:00:00", open_ports=[554])
    assert "Camera" in dtype


@pytest.mark.asyncio
async def test_scan_subnet_mocked():
    arp_data = (
        "IP address       HW type     Flags       HW address            Mask     Device\n"
        "192.168.1.50     0x1         0x2         dc:a6:32:11:22:33     *        eth0\n"
        "192.168.1.1      0x1         0x2         50:c7:bf:aa:bb:cc     *        eth0\n"
    )

    with patch("builtins.open", mock_open(read_data=arp_data)), \
         patch("jarvis.network.scanner.get_local_ip_and_gateway", return_value=("192.168.1.10", "192.168.1.1")), \
         patch("jarvis.network.scanner.probe_ports", return_value=[80]), \
         patch("jarvis.network.scanner.resolve_hostname", return_value="rpi.local"):

        devices = await scan_subnet(subnet_base="192.168.1")
        assert len(devices) >= 2
        rpi = [d for d in devices if d.ip == "192.168.1.50"][0]
        assert rpi.mac == "dc:a6:32:11:22:33"
        assert "Raspberry Pi" in rpi.vendor


@pytest.mark.asyncio
async def test_network_hub_persistence(tmp_path):
    store_file = tmp_path / "network_cache.json"
    hub = NetworkHub(store_path=store_file)

    dev = NetworkDevice(
        ip="192.168.1.100",
        mac="00:11:22:33:44:55",
        hostname="server.local",
        vendor="Custom PC",
        device_type="Linux Server",
    )
    hub._devices[dev.ip] = dev
    hub._save_cache()

    # Load in new hub
    hub2 = NetworkHub(store_path=store_file)
    devices = hub2.list_devices()
    assert len(devices) == 1
    assert devices[0].ip == "192.168.1.100"
    assert devices[0].hostname == "server.local"


@pytest.mark.asyncio
async def test_builtin_network_tools(tmp_path):
    store_file = tmp_path / "tool_network.json"
    hub = NetworkHub(store_path=store_file)

    with patch("jarvis.tools.builtin.network_tools.get_network_hub", return_value=hub):
        # 1. WoL
        with patch.object(hub, "wake_on_lan", return_value=True):
            res_wol = await wake_on_lan("00:11:22:33:44:55")
            assert "successfully transmitted" in res_wol

        # 2. Ping
        with patch.object(hub, "ping", return_value={
            "host": "8.8.8.8",
            "reachable": True,
            "avg_ms": 14.5,
            "min_ms": 12.0,
            "max_ms": 16.0,
            "jitter_ms": 1.1,
            "packet_loss_percent": 0,
        }):
            res_ping = await ping_network_host("8.8.8.8")
            assert "ONLINE" in res_ping
            assert "14.5 ms" in res_ping

        # 3. Benchmark
        with patch.object(hub, "benchmark", new_callable=AsyncMock) as mock_bench:
            mock_bench.return_value = {
                "online": True,
                "quality_score": "EXCELLENT",
                "avg_latency_ms": 12.3,
                "jitter_ms": 0.8,
                "packet_loss_percent": 0,
                "dns_lookup_ms": 10.5,
                "dns_status": "optimal",
                "http_rtt_ms": 45.2,
            }
            res_b = await benchmark_network_speed()
            assert "EXCELLENT" in res_b
            assert "12.3 ms" in res_b

        # 4. Scan
        with patch.object(hub, "scan_network", new_callable=AsyncMock) as mock_scan:
            mock_scan.return_value = [
                NetworkDevice(ip="192.168.1.1", mac="50:c7:bf:11:22:33", device_type="Router", vendor="TP-Link"),
            ]
            res_scan = await scan_local_network()
            assert "192.168.1.1" in res_scan
            assert "Router" in res_scan

        # 5. List devices
        hub._devices["192.168.1.1"] = NetworkDevice(ip="192.168.1.1", mac="50:c7:bf:11:22:33", device_type="Router", vendor="TP-Link")
        res_list = await list_network_devices()
        assert "Cached Local Network Devices" in res_list


def test_cli_network_subcommands(capsys, tmp_path):
    from jarvis.cli.main import run_cli

    store_file = tmp_path / "cli_net.json"
    hub = NetworkHub(store_path=store_file)

    with patch("jarvis.network.hub.get_network_hub", return_value=hub):
        # Ping
        with patch.object(hub, "ping", return_value={"host": "1.1.1.1", "reachable": True, "avg_ms": 15.2, "min_ms": 12.0, "max_ms": 18.0, "jitter_ms": 1.5, "packet_loss_percent": 0}):
            code = run_cli(["network", "ping", "1.1.1.1"])
            assert code == 0
            out = capsys.readouterr().out
            assert "Ping statistics for 1.1.1.1" in out

        # WoL
        with patch.object(hub, "wake_on_lan", return_value=True):
            code = run_cli(["network", "wol", "00:11:22:33:44:55"])
            assert code == 0
            out = capsys.readouterr().out
            assert "Magic packet successfully sent" in out

        # Bench
        with patch.object(hub, "benchmark", new_callable=AsyncMock) as mock_bench:
            mock_bench.return_value = {
                "online": True,
                "quality_score": "GOOD",
                "avg_latency_ms": 28.5,
                "jitter_ms": 2.1,
                "packet_loss_percent": 0,
                "dns_lookup_ms": 18.0,
                "dns_status": "optimal",
                "http_rtt_ms": 65.0,
            }
            code = run_cli(["network", "bench"])
            assert code == 0
            out = capsys.readouterr().out
            assert "JARVIS Network Diagnostic Report" in out
