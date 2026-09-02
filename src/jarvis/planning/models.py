from pydantic import BaseModel
from jarvis.tasks.models import TaskStep

class PlanSpec(BaseModel):
    goal: str
    steps: list[TaskStep]
