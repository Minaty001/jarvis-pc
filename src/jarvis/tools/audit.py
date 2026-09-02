from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Set

logger = logging.getLogger("jarvis.audit")

SECRET_KEYS: Set[str] = {"api_key", "token", "password", "secret", "authorization", "key"}

SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[a-zA-Z0-9_-]+"),
    re.compile(r"eyJ[a-zA-Z0-9_-]+"),
    re.compile(r"gh[pous]_[a-zA-Z0-9_-]+"),
    re.compile(r"xox[baprs]-[a-zA-Z0-9_-]+"),
]


def redact_secrets(data: Any) -> Any:
    """Recursively sanitize sensitive key names or secret string values in data structures."""
    if isinstance(data, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(sk in k_lower for sk in SECRET_KEYS):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = redact_secrets(v)
        return cleaned
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(redact_secrets(item) for item in data)
    elif isinstance(data, set):
        return {redact_secrets(item) for item in data}
    elif isinstance(data, str):
        if any(sk in data.lower() for sk in SECRET_KEYS):
            return "[REDACTED]"
        res = data
        for pat in SECRET_PATTERNS:
            res = pat.sub("[REDACTED]", res)
        return res
    else:
        return data


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
