import logging
import pytest
from pydantic import ValidationError

from jarvis.config.defaults import (
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    DEFAULT_ENVIRONMENT,
    DEFAULT_HOST,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_REQUEST_BYTES,
    DEFAULT_PORT,
)
from jarvis.config.settings import Settings, get_settings
from jarvis.logging import SecretRedactingFormatter, configure_logging


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("JARVIS_PORT", "9000")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.port == 9000
    assert settings.environment == DEFAULT_ENVIRONMENT
    assert settings.host == DEFAULT_HOST
    assert settings.log_level == DEFAULT_LOG_LEVEL
    assert settings.api_token is None
    assert settings.max_request_bytes == DEFAULT_MAX_REQUEST_BYTES
    assert settings.command_timeout_seconds == DEFAULT_COMMAND_TIMEOUT_SECONDS
    get_settings.cache_clear()


def test_settings_env_overrides(monkeypatch):
    monkeypatch.setenv("JARVIS_ENVIRONMENT", "staging")
    monkeypatch.setenv("JARVIS_HOST", "0.0.0.0")
    monkeypatch.setenv("JARVIS_PORT", "8080")
    monkeypatch.setenv("JARVIS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("JARVIS_API_TOKEN", "super-secret-token")
    monkeypatch.setenv("JARVIS_MAX_REQUEST_BYTES", "2048")
    monkeypatch.setenv("JARVIS_COMMAND_TIMEOUT_SECONDS", "45.5")

    get_settings.cache_clear()
    settings = get_settings()
    assert settings.environment == "staging"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8080
    assert settings.log_level == "DEBUG"
    assert settings.api_token == "super-secret-token"
    assert settings.max_request_bytes == 2048
    assert settings.command_timeout_seconds == 45.5
    get_settings.cache_clear()


def test_settings_validation_errors():
    with pytest.raises(ValidationError):
        Settings(port=70000)

    with pytest.raises(ValidationError):
        Settings(port=0)

    with pytest.raises(ValidationError):
        Settings(max_request_bytes=100)

    with pytest.raises(ValidationError):
        Settings(command_timeout_seconds=0.0)

    with pytest.raises(ValidationError):
        Settings(command_timeout_seconds=500.0)


def test_configure_logging(capsys):
    configure_logging(level="DEBUG")
    logger = logging.getLogger("jarvis.test")
    logger.debug("test debug message")
    logger.info("api_key=secret12345")

    captured = capsys.readouterr()
    assert "test debug message" in captured.out
    assert "api_key: [REDACTED]" in captured.out
    assert "secret12345" not in captured.out


def test_secret_redacting_formatter():
    formatter = SecretRedactingFormatter("%(levelname)s %(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="token='my-secret-token-123'",
        args=(),
        exc_info=None,
    )
    result = formatter.format(record)
    assert "token: [REDACTED]" in result
    assert "my-secret-token-123" not in result
