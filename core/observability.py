"""
Observability — Structured logging, tracing, and metrics for the cognitive engine.
"""

import time
import json
from typing import Any, Optional
from collections import defaultdict

from config.logger import get_logger

logger = get_logger("observability")


class MetricsCollector:
    """Collects and aggregates metrics across the system."""

    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._timers: dict[str, list[float]] = defaultdict(list)
        self._start_time = time.time()

    def inc(self, name: str, value: int = 1) -> None:
        self._counters[name] += value

    def set(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def timer(self, name: str, duration: float) -> None:
        self._timers[name].append(duration)
        if len(self._timers[name]) > 1000:
            self._timers[name] = self._timers[name][-1000:]

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    def get_timer_stats(self, name: str) -> dict:
        values = self._timers.get(name, [])
        if not values:
            return {"count": 0, "avg": 0, "min": 0, "max": 0}
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }

    def snapshot(self) -> dict:
        uptime = time.time() - self._start_time
        timers = {name: self.get_timer_stats(name) for name in self._timers}
        return {
            "uptime_seconds": uptime,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "timers": timers,
        }

    def summary(self) -> str:
        uptime = time.time() - self._start_time
        lines = [f"Uptime: {uptime:.0f}s"]
        for name, count in sorted(self._counters.items()):
            lines.append(f"  {name}: {count}")
        for name, val in sorted(self._gauges.items()):
            lines.append(f"  {name}: {val:.2f}")
        return "\n".join(lines)


class TraceSpan:
    """A single trace span for tracking operation timing."""

    def __init__(self, name: str, parent: Optional["TraceSpan"] = None):
        self.name = name
        self.parent = parent
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.attributes: dict[str, Any] = {}
        self.events: list[dict] = []

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[dict] = None) -> None:
        self.events.append({"name": name, "attributes": attributes or {}, "time": time.time()})

    def finish(self) -> float:
        self.end_time = time.time()
        return self.end_time - self.start_time

    @property
    def duration(self) -> float:
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "start_time": self.start_time,
            "duration": self.duration,
            "attributes": self.attributes,
            "events": self.events,
        }


class Tracer:
    """Distributed-style tracer for cognitive engine operations."""

    def __init__(self):
        self._spans: list[TraceSpan] = []
        self._active: Optional[TraceSpan] = None

    def start_span(self, name: str) -> TraceSpan:
        span = TraceSpan(name, parent=self._active)
        self._spans.append(span)
        self._active = span
        return span

    def end_span(self, span: TraceSpan) -> float:
        duration = span.finish()
        if self._active == span:
            self._active = span.parent
        return duration

    def get_recent(self, limit: int = 20) -> list[dict]:
        return [s.to_dict() for s in self._spans[-limit:]]

    def clear(self) -> None:
        self._spans.clear()


# Global instances
metrics = MetricsCollector()
tracer = Tracer()
