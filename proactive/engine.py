"""
Proactive Engine — Monitors context and triggers suggestions/actions without explicit requests.
Implements anticipation, reminders, anomaly detection, and learned behaviors.
"""

import asyncio
import time
from typing import Any, Callable, Optional

from config.logger import get_logger
from perception.event_bus import event_bus
from perception.event_models import Event, EventType, EventSeverity, make_event

logger = get_logger("proactive.engine")


class ProactiveRule:
    """A rule that triggers proactive behavior when conditions are met."""

    def __init__(
        self,
        name: str,
        condition: Callable[["ProactiveContext"], bool],
        action: Callable[["ProactiveContext"], Any],
        cooldown: float = 300.0,
        description: str = "",
    ):
        self.name = name
        self.condition = condition
        self.action = action
        self.cooldown = cooldown
        self.description = description
        self.last_triggered = 0.0
        self.trigger_count = 0

    def can_trigger(self, ctx: "ProactiveContext") -> bool:
        now = time.time()
        if now - self.last_triggered < self.cooldown:
            return False
        try:
            result = self.condition(ctx)
            return bool(result)
        except Exception as e:
            logger.error("Rule condition error for '%s': %s", self.name, e)
            return False

    async def execute(self, ctx: "ProactiveContext") -> Any:
        self.last_triggered = time.time()
        self.trigger_count += 1
        try:
            return await self.action(ctx)
        except Exception as e:
            logger.error("Rule action error for '%s': %s", self.name, e)
            return None


class ProactiveContext:
    """Context available to proactive rules."""

    def __init__(self):
        self.system_metrics: dict = {}
        self.focused_app: str = ""
        self.recent_events: list[dict] = []
        self.user_idle_seconds: float = 0.0
        self.time_of_day: str = ""
        self.active_tasks: int = 0
        self.memory_summary: str = ""


class ProactiveEngine:
    """Monitors context and triggers proactive rules."""

    def __init__(self, check_interval: float = 30.0):
        self.check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._rules: list[ProactiveRule] = []
        self._context = ProactiveContext()
        self._callbacks: list[Callable] = []
        self._last_user_activity = time.time()

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        self._register_default_rules()
        logger.info("Proactive engine started (%d rules)", len(self._rules))

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Proactive engine stopped")

    def add_rule(self, rule: ProactiveRule) -> None:
        self._rules.append(rule)

    def add_callback(self, callback: Callable) -> None:
        """Add callback to receive proactive suggestions."""
        self._callbacks.append(callback)

    def notify_user_activity(self) -> None:
        self._last_user_activity = time.time()

    def update_context(self, **kwargs) -> None:
        """Update the proactive context."""
        for k, v in kwargs.items():
            if hasattr(self._context, k):
                setattr(self._context, k, v)

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                self._context.user_idle_seconds = time.time() - self._last_user_activity
                self._context.time_of_day = self._get_time_of_day()

                for rule in self._rules:
                    if rule.can_trigger(self._context):
                        logger.info("Proactive rule triggered: %s", rule.name)
                        result = await rule.execute(self._context)
                        if result:
                            await self._notify_suggestion(rule.name, result)

                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Proactive monitor error: %s", e)
                await asyncio.sleep(self.check_interval)

    async def _notify_suggestion(self, rule_name: str, suggestion: Any) -> None:
        """Notify callbacks and emit event for a proactive suggestion."""
        for cb in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(rule_name, suggestion)
                else:
                    cb(rule_name, suggestion)
            except Exception as e:
                logger.error("Callback error: %s", e)

        await event_bus.publish(make_event(
            EventType.USER, "proactive_engine",
            {"rule": rule_name, "suggestion": str(suggestion)},
            EventSeverity.INFO,
        ))

    def _get_time_of_day(self) -> str:
        hour = time.localtime().tm_hour
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        return "night"

    def _register_default_rules(self) -> None:
        """Register built-in proactive rules."""

        # Idle reminder
        def idle_check(ctx: ProactiveContext) -> bool:
            return ctx.user_idle_seconds > 1800  # 30 min

        async def idle_action(ctx: ProactiveContext) -> str:
            return "You've been idle for a while. Need help with anything?"

        self.add_rule(ProactiveRule(
            name="idle_reminder",
            condition=idle_check,
            action=idle_action,
            cooldown=1800,
            description="Remind user after extended idle time",
        ))

        # High CPU warning
        def high_cpu_check(ctx: ProactiveContext) -> bool:
            return ctx.system_metrics.get("cpu_percent", 0) > 90

        async def high_cpu_action(ctx: ProactiveContext) -> str:
            cpu = ctx.system_metrics.get("cpu_percent", 0)
            return f"CPU usage is high ({cpu:.0f}%). Would you like me to check what's using it?"

        self.add_rule(ProactiveRule(
            name="high_cpu_warning",
            condition=high_cpu_check,
            action=high_cpu_action,
            cooldown=600,
            description="Warn when CPU usage is very high",
        ))

        # Low disk space
        def low_disk_check(ctx: ProactiveContext) -> bool:
            return ctx.system_metrics.get("disk_free_gb", 100) < 5

        async def low_disk_action(ctx: ProactiveContext) -> str:
            free = ctx.system_metrics.get("disk_free_gb", 0)
            return f"Disk space is low ({free:.1f} GB free). Would you like me to help clean up?"

        self.add_rule(ProactiveRule(
            name="low_disk_warning",
            condition=low_disk_check,
            action=low_disk_action,
            cooldown=3600,
            description="Warn when disk space is critically low",
        ))

        # Morning greeting
        def morning_check(ctx: ProactiveContext) -> bool:
            return ctx.time_of_day == "morning" and ctx.user_idle_seconds < 30

        async def morning_action(ctx: ProactiveContext) -> str:
            return "Good morning! I'm ready to help with your tasks today."

        self.add_rule(ProactiveRule(
            name="morning_greeting",
            condition=morning_check,
            action=morning_action,
            cooldown=86400,
            description="Greet user in the morning",
        ))

    def get_rules(self) -> list[dict]:
        return [
            {"name": r.name, "description": r.description, "trigger_count": r.trigger_count}
            for r in self._rules
        ]

    def get_summary(self) -> str:
        return f"Rules: {len(self._rules)} | Idle: {self._context.user_idle_seconds:.0f}s"


proactive_engine = ProactiveEngine()
