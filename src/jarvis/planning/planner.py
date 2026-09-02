from __future__ import annotations

from jarvis.tasks.models import TaskPlan, TaskStep


class TaskPlanner:
    async def create_plan(self, user_request: str) -> TaskPlan:
        req = user_request.lower()
        steps = []
        if "firefox" in req:
            steps.append(
                TaskStep(
                    id="step-1",
                    tool="open_application",
                    arguments={"name": "firefox"},
                )
            )
        else:
            steps.append(
                TaskStep(id="step-1", tool="system_info", arguments={})
            )
        return TaskPlan(id="plan-auto", steps=steps)
