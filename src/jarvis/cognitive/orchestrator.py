from __future__ import annotations

from typing import Any, Dict, Optional
from jarvis.cognitive.context import ExecutionContext
from jarvis.planning.planner import TaskPlanner
from jarvis.tasks.manager import TaskManager


class Orchestrator:
    def __init__(self, planner: TaskPlanner, manager: TaskManager) -> None:
        self.planner = planner
        self.manager = manager

    async def process_request(
        self,
        user_request: str,
        context: Optional[ExecutionContext] = None,
    ) -> Dict[str, Any]:
        plan = await self.planner.create_plan(user_request)
        return await self.manager.execute_plan(plan, context=context)
