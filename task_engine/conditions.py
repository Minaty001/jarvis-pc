# task_engine/conditions.py
"""Condition Engine — event/condition-driven task triggers."""
from __future__ import annotations
import asyncio, time, psutil
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional
from config.logger import get_logger

logger = get_logger("task_engine.conditions")


@dataclass
class Condition:
    name: str
    check: Callable[["ConditionContext"], bool]
    action: Callable[["ConditionContext"], Awaitable[Any]]
    cooldown: float = 300.0
    last_fired: float = 0.0


class ConditionContext:
    def __init__(self):
        self.battery_percent: float = 100.0
        self.cpu_percent: float = 0.0
        self.network_available: bool = True
        self.user_idle_seconds: float = 0.0


class ConditionEngine:
    """Polls system state and fires registered condition callbacks."""

    def __init__(self, poll_interval: float = 30.0):
        self.poll_interval = poll_interval
        self._conditions: list[Condition] = []
        self._running = False
        self._ctx = ConditionContext()
        self._register_builtins()

    def _register_builtins(self):
        self.add_condition("battery_low",
            lambda ctx: ctx.battery_percent < 20.0,
            self._notify_battery_low, cooldown=600)
        self.add_condition("cpu_high",
            lambda ctx: ctx.cpu_percent > 80.0,
            self._notify_cpu_high, cooldown=300)

    async def _notify_battery_low(self, ctx): 
        logger.warning("Battery low: %.0f%%", ctx.battery_percent)
    async def _notify_cpu_high(self, ctx):
        logger.warning("CPU high: %.0f%%", ctx.cpu_percent)

    def add_condition(self, name: str, check_fn, action_fn, cooldown: float = 300.0):
        self._conditions.append(Condition(name=name, check=check_fn, action=action_fn, cooldown=cooldown))

    def list_conditions(self) -> list[dict]:
        return [{"name": c.name, "cooldown": c.cooldown} for c in self._conditions]

    async def start(self):
        self._running = True
        while self._running:
            self._update_context()
            now = time.time()
            for cond in self._conditions:
                if now - cond.last_fired < cond.cooldown:
                    continue
                try:
                    if cond.check(self._ctx):
                        cond.last_fired = now
                        await cond.action(self._ctx)
                except Exception as e:
                    logger.error("Condition %s error: %s", cond.name, e)
            await asyncio.sleep(self.poll_interval)

    def stop(self):
        self._running = False

    def _update_context(self):
        try:
            battery = psutil.sensors_battery()
            if battery:
                self._ctx.battery_percent = battery.percent
            self._ctx.cpu_percent = psutil.cpu_percent(interval=None)
        except Exception:
            pass


condition_engine = ConditionEngine()
