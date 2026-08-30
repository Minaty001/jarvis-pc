"""Event Models — Structured event definitions for all perception categories."""

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EventType(Enum):
    SYSTEM = "system"
    APPLICATION = "application"
    WINDOW = "window"
    FILE = "file"
    NETWORK = "network"
    USER = "user"
    TASK = "task"
    ERROR = "error"
    SECURITY = "security"


class EventSeverity(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Event:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: float = field(default_factory=time.time)
    type: EventType = EventType.SYSTEM
    source: str = ""
    severity: EventSeverity = EventSeverity.INFO
    payload: dict = field(default_factory=dict)
    correlation_id: str = ""
    processed: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "type": self.type.value,
            "source": self.source,
            "severity": self.severity.value,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "processed": self.processed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        return cls(
            id=data.get("id", str(uuid.uuid4())[:12]),
            timestamp=data.get("timestamp", time.time()),
            type=EventType(data.get("type", "system")),
            source=data.get("source", ""),
            severity=EventSeverity(data.get("severity", "info")),
            payload=data.get("payload", {}),
            correlation_id=data.get("correlation_id", ""),
        )


def make_event(
    event_type: EventType,
    source: str,
    payload: dict,
    severity: EventSeverity = EventSeverity.INFO,
    correlation_id: str = "",
) -> Event:
    """Factory function for creating events."""
    return Event(
        type=event_type,
        source=source,
        payload=payload,
        severity=severity,
        correlation_id=correlation_id,
    )
