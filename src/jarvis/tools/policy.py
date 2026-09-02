"""Security risk levels for tool execution policy enforcement."""

from enum import Enum


class RiskLevel(str, Enum):
    """Risk levels governing execution permissions and confirmation requirements."""
    SAFE = "SAFE"
    CONFIRM = "CONFIRM"
    PRIVILEGED = "PRIVILEGED"
    FORBIDDEN = "FORBIDDEN"
