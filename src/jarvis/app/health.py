from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from jarvis.app.application import Application

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    status: str = "healthy"
    started: bool = False
    components: dict[str, Any] = field(default_factory=dict)


async def check_health(app: Application | None = None) -> HealthStatus:
    """Perform system health checks on the Application and its subsystems."""
    if app is None:
        return HealthStatus(status="healthy", started=False)

    components_health: dict[str, Any] = {}
    is_healthy = True

    for name in ("scheduler", "voice", "api"):
        subsystem = getattr(app, name, None)
        if subsystem is None:
            continue

        if hasattr(subsystem, "health_check") and callable(subsystem.health_check):
            try:
                res = await subsystem.health_check()
                components_health[name] = res
            except Exception as exc:
                logger.warning("Health check failed for subsystem %s: %s", name, exc)
                components_health[name] = {"status": "unhealthy", "error": str(exc)}
                is_healthy = False
        else:
            components_health[name] = {"status": "ok"}

    overall_status = "healthy" if is_healthy else "unhealthy"
    return HealthStatus(
        status=overall_status,
        started=app.is_started,
        components=components_health,
    )
