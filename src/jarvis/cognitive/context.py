from dataclasses import dataclass, field

@dataclass(frozen=True)
class ExecutionContext:
    session_id: str
    task_id: str
    user_id: str
    request_id: str
    permissions: frozenset[str] = field(default_factory=frozenset)
