from __future__ import annotations

import json
import logging
from typing import Any, Dict, Set

logger = logging.getLogger("jarvis.audit")

SECRET_KEYS: Set[str] = {"api_key", "token", "password", "secret", "authorization", "key"}


def redact_secrets(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize sensitive key names or secret string values in dictionary data."""
    cleaned: Dict[str, Any] = {}
    for k, v in data.items():
        k_lower = k.lower()
        if any(sk in k_lower for sk in SECRET_KEYS) or (isinstance(v, str) and any(sk in v.lower() for sk in SECRET_KEYS)):
            cleaned[k] = "[REDACTED]"
        elif isinstance(v, dict):
            cleaned[k] = redact_secrets(v)
        else:
            cleaned[k] = v
    return cleaned


class AuditLogger:
    """Structured audit logger recording tool execution with secret redaction."""

    def __init__(self, audit_logger: logging.Logger | None = None) -> None:
        self.logger = audit_logger or logger

    def log_execution(
        self,
        request_id: str,
        tool_name: str,
        risk: str,
        status: str,
        arguments: Dict[str, Any],
    ) -> None:
        safe_args = redact_secrets(arguments)
        record = {
            "request_id": request_id,
            "tool": tool_name,
            "risk": risk,
            "status": status,
            "arguments": safe_args,
        }
        self.logger.info("AUDIT %s", json.dumps(record))
