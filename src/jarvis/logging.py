"""Structured logging setup for JARVIS with secret safety redaction."""

import logging
import re
import sys

# Common regex patterns to match secrets (API keys, tokens, secrets)
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret|auth)\s*[:=]\s*['\"]?([^\s'\"&]+)['\"]?"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
]


class SecretRedactingFormatter(logging.Formatter):
    """Formatter that redacts sensitive values such as API keys and tokens from log output."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        for pattern in SECRET_PATTERNS:
            if pattern.groups > 0:
                formatted = pattern.sub(r"\g<1>: [REDACTED]", formatted)
            else:
                formatted = pattern.sub("[REDACTED]", formatted)
        return formatted


def configure_logging(level: str = "INFO") -> None:
    """Configure structured logging for JARVIS with output to sys.stdout."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s %(levelname)s %(name)s %(process)d %(message)s"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(SecretRedactingFormatter(fmt))

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
