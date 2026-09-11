"""Proactive Background Engine for JARVIS PC.

Autonomously monitors system vitals (RAM, Disk, CPU, Battery) and context,
evaluating cooldown-guarded rules and firing native desktop notifications.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

import psutil

from jarvis.config.settings import Settings, get_settings
from jarvis.system.notifications import notify

logger = logging.getLogger(__name__)


class ProactiveContext:
    """Snapshot of system health and context metrics."""

    def __init__(self) -> None:
        self.cpu_percent: float = 0.0
        self.ram_percent: float = 0.0
        self.disk_percent: float = 0.0
        self.battery_percent: Optional[float] = None
        self.battery_plugged: Optional[bool] = None
        self.time_of_day: str = "day"
        self.top_process: str = ""

    def refresh(self) -> None:
        """Poll psutil for real-time system metrics."""
        try:
            self.cpu_percent = psutil.cpu_percent(interval=None)
            self.ram_percent = psutil.virtual_memory().percent
            self.disk_percent = psutil.disk_usage("/").percent

            # Battery (optional, may not exist on desktops)
            battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
            if battery:
                self.battery_percent = battery.percent
                self.battery_plugged = battery.power_plugged
            else:
                self.battery_percent = None
                self.battery_plugged = None

            # Time of day
            hour = datetime.datetime.now().hour
            if 5 <= hour < 12:
                self.time_of_day = "morning"
            elif 12 <= hour < 17:
                self.time_of_day = "afternoon"
            elif 17 <= hour < 22:
                self.time_of_day = "evening"
            else:
                self.time_of_day = "night"

            # Top memory process (if RAM pressure)
            if self.ram_percent > 70.0:
                try:
                    procs = sorted(
                        psutil.process_iter(["name", "memory_percent"]),
                        key=lambda p: p.info.get("memory_percent", 0.0) or 0.0,
                        reverse=True,
                    )
                    top = procs[0].info.get("name", "") if procs else ""
                    self.top_process = top or ""
                except Exception:
                    self.top_process = ""
        except Exception as exc:
            logger.debug("Error updating proactive context: %s", exc)


class ProactiveRule:
    """Cooldown-guarded autonomous condition and action."""

    def __init__(
        self,
        name: str,
        condition: Callable[[ProactiveContext], bool],
        action: Callable[[ProactiveContext], Awaitable[None] | None],
        cooldown: float = 600.0,
        description: str = "",
    ) -> None:
        self.name = name
        self.condition = condition
        self.action = action
        self.cooldown = cooldown
        self.description = description
        self.last_triggered: float = 0.0
        self.trigger_count: int = 0

    def can_trigger(self, ctx: ProactiveContext) -> bool:
        now = time.time()
        if now - self.last_triggered < self.cooldown:
            return False
        try:
            return bool(self.condition(ctx))
        except Exception as exc:
            logger.error("Rule condition error for '%s': %s", self.name, exc)
            return False

    async def execute(self, ctx: ProactiveContext) -> None:
        self.last_triggered = time.time()
        self.trigger_count += 1
        try:
            res = self.action(ctx)
            if asyncio.iscoroutine(res):
                await res
        except Exception as exc:
            logger.error("Rule action error for '%s': %s", self.name, exc)


class ProactiveEngine:
    """Background engine that periodically evaluates proactive rules."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.check_interval = self.settings.proactive_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._context = ProactiveContext()
        self._rules: List[ProactiveRule] = []
        self._register_default_rules()

    @property
    def is_running(self) -> bool:
        return self._running

    def _register_default_rules(self) -> None:
        ram_th = self.settings.proactive_ram_threshold
        disk_th = self.settings.proactive_disk_threshold
        cpu_th = self.settings.proactive_cpu_threshold
        bat_th = self.settings.proactive_battery_threshold

        # 1. High Memory Alert (Default 85%)
        self.add_rule(
            ProactiveRule(
                name="high_memory",
                condition=lambda ctx: ctx.ram_percent >= ram_th,
                action=lambda ctx: notify(
                    "JARVIS — Memory Warning",
                    f"System RAM is at {ctx.ram_percent:.1f}% capacity"
                    + (f" (top: {ctx.top_process})" if ctx.top_process else "")
                    + ".",
                    urgency="critical",
                ),
                cooldown=600.0,
                description=f"Alerts when RAM usage exceeds {ram_th:.0f}%",
            )
        )

        # 2. Low Disk Space Alert (Default 90%)
        self.add_rule(
            ProactiveRule(
                name="low_disk",
                condition=lambda ctx: ctx.disk_percent >= disk_th,
                action=lambda ctx: notify(
                    "JARVIS — Low Disk Space Alert",
                    f"Root partition is at {ctx.disk_percent:.1f}% capacity. Consider cleaning caches or temp files.",
                    urgency="critical",
                ),
                cooldown=3600.0,
                description=f"Alerts when disk usage exceeds {disk_th:.0f}%",
            )
        )

        # 3. High CPU Alert (Default 90%)
        self.add_rule(
            ProactiveRule(
                name="runaway_cpu",
                condition=lambda ctx: ctx.cpu_percent >= cpu_th,
                action=lambda ctx: notify(
                    "JARVIS — CPU Load Warning",
                    f"System CPU load is at {ctx.cpu_percent:.1f}%. High compute tasks running.",
                    urgency="normal",
                ),
                cooldown=600.0,
                description=f"Alerts when CPU load exceeds {cpu_th:.0f}%",
            )
        )

        # 4. Low Battery Warning (Default 15%)
        self.add_rule(
            ProactiveRule(
                name="low_battery",
                condition=lambda ctx: (
                    ctx.battery_percent is not None
                    and ctx.battery_percent <= bat_th
                    and ctx.battery_plugged is False
                ),
                action=lambda ctx: notify(
                    "JARVIS — Low Battery Warning",
                    f"Battery level is at {ctx.battery_percent:.0f}%. Please plug in the charger.",
                    urgency="critical",
                ),
                cooldown=900.0,
                description=f"Alerts when battery falls below {bat_th:.0f}%",
            )
        )

        # 5. Morning Briefing Greeting
        self.add_rule(
            ProactiveRule(
                name="morning_briefing",
                condition=lambda ctx: ctx.time_of_day == "morning",
                action=lambda ctx: notify(
                    "JARVIS Online",
                    "Good morning! Systems are nominal and JARVIS is ready to assist.",
                    urgency="low",
                ),
                cooldown=64800.0,  # 18 hours
                description="Greets user during morning hours",
            )
        )

    def add_rule(self, rule: ProactiveRule) -> None:
        self._rules.append(rule)

    def list_rules(self) -> List[Dict[str, Any]]:
        now = time.time()
        return [
            {
                "name": r.name,
                "description": r.description,
                "cooldown": r.cooldown,
                "trigger_count": r.trigger_count,
                "last_triggered": r.last_triggered,
                "in_cooldown": (now - r.last_triggered) < r.cooldown if r.last_triggered > 0 else False,
            }
            for r in self._rules
        ]

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Proactive engine started (%d rules, interval=%.1fs)", len(self._rules), self.check_interval)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Proactive engine stopped")

    async def check_rules_once(self) -> List[str]:
        """Poll metrics once and execute any ready rules. Returns names of triggered rules."""
        self._context.refresh()
        triggered = []
        for rule in self._rules:
            if rule.can_trigger(self._context):
                logger.info("Proactive rule triggered: %s", rule.name)
                await rule.execute(self._context)
                triggered.append(rule.name)
        return triggered

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.check_rules_once()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in proactive loop: %s", exc)
                await asyncio.sleep(self.check_interval)
