"""Security tests for secret redaction in logging."""

import logging
from jarvis.logging import SecretRedactingFormatter


def test_formatter_redacts_api_key():
    """Verify SecretRedactingFormatter redacts tokens matching secret patterns."""
    formatter = SecretRedactingFormatter("%(message)s")
    record = logging.LogRecord(
        "test", logging.INFO, "", 0, "token=sk-1234567890abcdef12345678", (), None
    )
    formatted = formatter.format(record)
    assert "sk-1234567890" not in formatted
    assert "[REDACTED]" in formatted


def test_formatter_redacts_kv_secrets():
    """Verify key-value formatted secrets like api_key: secret are redacted."""
    formatter = SecretRedactingFormatter("%(message)s")
    record = logging.LogRecord(
        "test", logging.INFO, "", 0, "api_key='my-super-secret-key'", (), None
    )
    formatted = formatter.format(record)
    assert "my-super-secret-key" not in formatted
    assert "[REDACTED]" in formatted


def test_formatter_preserves_normal_messages():
    """Verify normal un-sensitive log messages pass through unmodified."""
    formatter = SecretRedactingFormatter("%(message)s")
    record = logging.LogRecord(
        "test", logging.INFO, "", 0, "System initialized successfully", (), None
    )
    formatted = formatter.format(record)
    assert formatted == "System initialized successfully"
