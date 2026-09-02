from typing import Any
from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    tool: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False


class ExecuteResponse(BaseModel):
    ok: bool
    result: Any = None
