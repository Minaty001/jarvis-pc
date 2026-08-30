"""
System Monitor — Tracks CPU, memory, disk, network, and process metrics.
Publishes system events to the event bus.
"""

import asyncio
import time
import os
import json
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None

from config.logger import get_logger
from perception.event_bus import event_bus
from perception.event_models import Event, EventType, EventSeverity, make_event

logger = get_logger("perception.system_monitor")


class SystemMonitor:
    """Monitors system resources and publishes events on significant changes."""

    def __init__(
        self,
        poll_interval: float = 5.0,
        cpu_warn_threshold: float = 80.0,
        cpu_crit_threshold: float = 95.0,
        mem_warn_threshold: float = 80.0,
        mem_crit_threshold: float = 95.0,
        disk_warn_threshold: float = 85.0,
    ):
        self.poll_interval = poll_interval
        self.cpu_warn = cpu_warn_threshold
        self.cpu_crit = cpu_crit_threshold
        self.mem_warn = mem_warn_threshold
        self.mem_crit = mem_crit_threshold
        self.disk_warn = disk_warn_threshold
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._prev_net = None
        self._last_snapshot: dict = {}

    async def start(self) -> None:
        if psutil is None:
            logger.warning("psutil not installed; system monitor disabled")
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("System monitor started (interval=%.1fs)", self.poll_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("System monitor stopped")

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                snapshot = self._collect_snapshot()
                self._last_snapshot = snapshot
                await self._evaluate(snapshot)
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Monitor loop error: %s", e)
                await asyncio.sleep(self.poll_interval)

    def _collect_snapshot(self) -> dict:
        """Collect current system metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            net = psutil.net_io_counters()

            # Network rate
            net_rate = {"bytes_sent_rate": 0, "bytes_recv_rate": 0}
            if self._prev_net:
                dt = self.poll_interval
                net_rate["bytes_sent_rate"] = (net.bytes_sent - self._prev_net.bytes_sent) / dt
                net_rate["bytes_recv_rate"] = (net.bytes_recv - self._prev_net.bytes_recv) / dt
            self._prev_net = net

            # Top processes by CPU
            top_procs = []
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    info = proc.info
                    if info["cpu_percent"] and info["cpu_percent"] > 0:
                        top_procs.append(info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            top_procs.sort(key=lambda p: p.get("cpu_percent", 0), reverse=True)

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": mem.percent,
                "memory_used_gb": round(mem.used / (1024**3), 2),
                "memory_total_gb": round(mem.total / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "net_sent_total": net.bytes_sent,
                "net_recv_total": net.bytes_recv,
                "net_sent_rate": net_rate["bytes_sent_rate"],
                "net_recv_rate": net_rate["bytes_recv_rate"],
                "top_processes": top_procs[:5],
                "uptime": time.time() - psutil.boot_time(),
            }
        except Exception as e:
            logger.error("Failed to collect snapshot: %s", e)
            return {}

    async def _evaluate(self, snapshot: dict) -> None:
        """Evaluate snapshot and publish events for thresholds."""
        if not snapshot:
            return

        cpu = snapshot.get("cpu_percent", 0)
        mem = snapshot.get("memory_percent", 0)
        disk = snapshot.get("disk_percent", 0)

        # CPU events
        if cpu >= self.cpu_crit:
            await event_bus.publish(make_event(
                EventType.SYSTEM, "system_monitor",
                {"metric": "cpu", "value": cpu, "status": "critical"},
                EventSeverity.CRITICAL,
            ))
        elif cpu >= self.cpu_warn:
            await event_bus.publish(make_event(
                EventType.SYSTEM, "system_monitor",
                {"metric": "cpu", "value": cpu, "status": "warning"},
                EventSeverity.WARNING,
            ))

        # Memory events
        if mem >= self.mem_crit:
            await event_bus.publish(make_event(
                EventType.SYSTEM, "system_monitor",
                {"metric": "memory", "value": mem, "status": "critical"},
                EventSeverity.CRITICAL,
            ))
        elif mem >= self.mem_warn:
            await event_bus.publish(make_event(
                EventType.SYSTEM, "system_monitor",
                {"metric": "memory", "value": mem, "status": "warning"},
                EventSeverity.WARNING,
            ))

        # Disk events
        if disk >= self.disk_warn:
            await event_bus.publish(make_event(
                EventType.SYSTEM, "system_monitor",
                {"metric": "disk", "value": disk, "status": "warning"},
                EventSeverity.WARNING,
            ))

    def get_snapshot(self) -> dict:
        """Get the most recent snapshot."""
        return dict(self._last_snapshot)

    def get_summary(self) -> str:
        """Human-readable system summary."""
        s = self._last_snapshot
        if not s:
            return "No system data collected yet"
        return (
            f"CPU: {s.get('cpu_percent', 0):.1f}% | "
            f"MEM: {s.get('memory_percent', 0):.1f}% ({s.get('memory_used_gb', 0):.1f}/{s.get('memory_total_gb', 0):.1f} GB) | "
            f"DISK: {s.get('disk_percent', 0):.1f}% ({s.get('disk_free_gb', 0):.1f} GB free)"
        )


system_monitor = SystemMonitor()
