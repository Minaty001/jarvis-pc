from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    CONFIRM = "CONFIRM"
    PRIVILEGED = "PRIVILEGED"
    FORBIDDEN = "FORBIDDEN"
