"""Builtin tools for Multi-Agent Swarm Orchestration and Background Subagent Execution."""

from __future__ import annotations

from typing import Any, Dict, List

from jarvis.cognitive.context import ExecutionContext
from jarvis.swarm.engine import get_swarm_engine
from jarvis.swarm.models import TaskStatus, WorkerRole


async def handle_spawn_background_worker(
    ctx: ExecutionContext,
    role: str = "general",
    instruction: str = "",
    name: str = "",
) -> Dict[str, Any]:
    """Spawn an autonomous background sub-agent worker to execute a task asynchronously."""
    if not instruction.strip():
        return {"success": False, "error": "Instruction cannot be empty."}

    engine = get_swarm_engine()
    task = await engine.spawn_worker(
        role=role,
        instruction=instruction,
        name=name,
    )
    return {
        "success": True,
        "task_id": task.id,
        "name": task.name,
        "role": task.role.value if isinstance(task.role, WorkerRole) else str(task.role),
        "status": task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
        "message": f"Background worker [{task.name}] spawned with ID '{task.id}'.",
    }


async def handle_list_swarm_tasks(
    ctx: ExecutionContext,
    status: str = "",
    role: str = "",
    limit: int = 10,
) -> Dict[str, Any]:
    """List recent and active background sub-agent tasks."""
    engine = get_swarm_engine()
    tasks = engine.list_tasks(status=status or None, role=role or None, limit=limit)
    return {
        "success": True,
        "count": len(tasks),
        "tasks": [
            {
                "id": t.id,
                "name": t.name,
                "role": t.role.value if isinstance(t.role, WorkerRole) else str(t.role),
                "status": t.status.value if isinstance(t.status, TaskStatus) else str(t.status),
                "progress_percent": t.progress_percent,
                "instruction": t.instruction,
                "created_at": t.created_at,
                "completed_at": t.completed_at,
            }
            for t in tasks
        ],
    }


async def handle_get_swarm_task_details(
    ctx: ExecutionContext,
    task_id: str = "",
) -> Dict[str, Any]:
    """Get full status, logs, and result output for a specific swarm task."""
    if not task_id.strip():
        return {"success": False, "error": "task_id is required."}

    engine = get_swarm_engine()
    task = engine.get_task(task_id.strip())
    if not task:
        return {"success": False, "error": f"Swarm task '{task_id}' not found."}

    return {
        "success": True,
        "task": task.to_dict(),
    }


async def handle_cancel_swarm_task(
    ctx: ExecutionContext,
    task_id: str = "",
) -> Dict[str, Any]:
    """Cancel an active background sub-agent worker."""
    if not task_id.strip():
        return {"success": False, "error": "task_id is required."}

    engine = get_swarm_engine()
    cancelled = await engine.cancel_task(task_id.strip())
    return {
        "success": cancelled,
        "task_id": task_id,
        "message": f"Task '{task_id}' cancelled." if cancelled else f"Could not cancel task '{task_id}' (not active or not found).",
    }


async def handle_decompose_swarm_goal(
    ctx: ExecutionContext,
    goal: str = "",
    max_workers: int = 3,
) -> Dict[str, Any]:
    """Decompose a high-level goal into parallel sub-agent tasks and execute them in the swarm."""
    if not goal.strip():
        return {"success": False, "error": "Goal cannot be empty."}

    engine = get_swarm_engine()
    tasks = await engine.decompose_and_dispatch(goal=goal, max_workers=max_workers)
    return {
        "success": True,
        "parent_goal": goal,
        "dispatched_tasks": [
            {
                "id": t.id,
                "name": t.name,
                "role": t.role.value if isinstance(t.role, WorkerRole) else str(t.role),
                "instruction": t.instruction,
            }
            for t in tasks
        ],
        "message": f"Decomposed goal into {len(tasks)} parallel background sub-agent workers.",
    }
