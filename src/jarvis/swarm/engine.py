"""Autonomous Swarm Orchestration Engine for JARVIS PC."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from jarvis.brain.client import ChatResult, LLMClient
from jarvis.swarm.models import SwarmTask, TaskStatus, WorkerRole
from jarvis.swarm.store import SwarmStore
from jarvis.swarm.worker import SubAgentWorker
from jarvis.system.notifications import notify
from jarvis.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_SWARM_ENGINE_SINGLETON: Optional[SwarmEngine] = None


class SwarmEngine:
    """Manages concurrent subagent workers, task delegation, and result aggregation."""

    def __init__(
        self,
        store: Optional[SwarmStore] = None,
        registry: Optional[ToolRegistry] = None,
        executor: Optional[Any] = None,
        max_concurrent_workers: int = 5,
    ) -> None:
        self.store = store or SwarmStore()
        self.registry = registry or ToolRegistry()
        self.executor = executor
        self.max_concurrent_workers = max_concurrent_workers
        self._active_workers: Dict[str, SubAgentWorker] = {}
        self._running_tasks: Dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    def list_tasks(
        self,
        status: Optional[str | TaskStatus] = None,
        role: Optional[str | WorkerRole] = None,
        limit: int = 50,
    ) -> List[SwarmTask]:
        """Query tasks from persistent store."""
        return self.store.list_tasks(status=status, role=role, limit=limit)

    def get_task(self, task_id: str) -> Optional[SwarmTask]:
        """Fetch task details and logs."""
        return self.store.get_task(task_id)

    async def spawn_worker(
        self,
        role: WorkerRole | str = WorkerRole.GENERAL,
        instruction: str = "",
        name: str = "",
        parent_goal: str = "",
        client: Optional[LLMClient] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SwarmTask:
        """Spawn and launch an asynchronous background sub-agent worker."""
        if isinstance(role, str):
            clean_role = role.strip().lower()
            role_enum = WorkerRole(clean_role) if clean_role in [r.value for r in WorkerRole] else WorkerRole.GENERAL
        else:
            role_enum = role

        task = SwarmTask(
            parent_goal=parent_goal,
            role=role_enum,
            instruction=instruction.strip(),
            name=name.strip() or f"{role_enum.value.capitalize()} Worker",
            metadata=metadata or {},
        )

        self.store.save_task(task)

        def _on_progress(updated_task: SwarmTask) -> None:
            self.store.save_task(updated_task)

        worker = SubAgentWorker(
            task=task,
            client=client,
            registry=self.registry,
            executor=self.executor,
            on_progress=_on_progress,
        )

        async with self._lock:
            self._active_workers[task.id] = worker
            async_task = asyncio.create_task(self._run_worker_wrapper(worker))
            self._running_tasks[task.id] = async_task

        return task

    async def _run_worker_wrapper(self, worker: SubAgentWorker) -> None:
        """Wrapper handling worker execution, persistence, and alerts."""
        task_id = worker.task.id
        try:
            completed_task = await worker.run()
            self.store.save_task(completed_task)

            # Fire desktop alert on completion
            if completed_task.status == TaskStatus.COMPLETED:
                try:
                    notify(
                        title=f"JARVIS Swarm: {completed_task.name} Finished",
                        body=completed_task.result[:120] if completed_task.result else "Task completed successfully.",
                    )
                except Exception as ex:
                    logger.debug("Desktop notification error: %s", ex)
            elif completed_task.status == TaskStatus.FAILED:
                try:
                    notify(
                        title=f"JARVIS Swarm: {completed_task.name} Failed",
                        body=str(completed_task.error)[:120],
                    )
                except Exception as ex:
                    logger.debug("Desktop notification error: %s", ex)

        except Exception as exc:
            logger.error("Error executing worker [%s]: %s", task_id, exc)
            worker.task.status = TaskStatus.FAILED
            worker.task.error = str(exc)
            self.store.save_task(worker.task)
        finally:
            async with self._lock:
                self._active_workers.pop(task_id, None)
                self._running_tasks.pop(task_id, None)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel an active background worker."""
        async with self._lock:
            worker = self._active_workers.get(task_id)
            async_task = self._running_tasks.get(task_id)

            if worker:
                worker.cancel()
                self.store.save_task(worker.task)

            if async_task and not async_task.done():
                async_task.cancel()
                return True

            task = self.store.get_task(task_id)
            if task and task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now(timezone.utc).isoformat()
                self.store.save_task(task)
                return True

            return False

    async def cancel_all(self) -> int:
        """Cancel all running swarm workers."""
        async with self._lock:
            active_ids = list(self._active_workers.keys())

        count = 0
        for tid in active_ids:
            if await self.cancel_task(tid):
                count += 1
        return count

    async def decompose_and_dispatch(
        self,
        goal: str,
        client: Optional[LLMClient] = None,
        max_workers: int = 3,
    ) -> List[SwarmTask]:
        """Decompose a high-level goal into parallel sub-tasks and launch them."""
        llm = client or LLMClient.from_settings()

        decomposition_prompt = (
            "You are the JARVIS Multi-Agent Swarm Architect. "
            "Decompose the following user goal into 2 to 4 parallel, specialized sub-agent tasks.\n"
            f"Goal: {goal}\n\n"
            "Respond ONLY with a valid JSON array of objects. Each object must have:\n"
            "- role: one of ['researcher', 'coder', 'system', 'writer', 'general']\n"
            "- name: short descriptive title\n"
            "- instruction: specific task instructions\n\n"
            "Example format:\n"
            '[\n  {"role": "researcher", "name": "PyTorch 2.5 Docs", "instruction": "Search for PyTorch 2.5 release notes"},\n'
            '  {"role": "coder", "name": "Benchmark Script", "instruction": "Write a benchmark script for GPU matrix multiplication"}\n]'
        )

        subtasks_data: List[Dict[str, Any]] = []

        try:
            resp = await llm.chat(
                messages=[{"role": "user", "content": decomposition_prompt}],
            )
            raw = resp.reply if hasattr(resp, "reply") else (resp.get("reply", "") if isinstance(resp, dict) else str(resp))
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            start = raw.find("[")
            end = raw.rfind("]")
            if start != -1 and end != -1:
                subtasks_data = json.loads(raw[start:end+1])
        except Exception as exc:
            logger.debug("Decomposition LLM fallback due to: %s", exc)

        if not subtasks_data:
            # Heuristic fallback: create 2 default tasks
            subtasks_data = [
                {
                    "role": "researcher",
                    "name": "Background Research",
                    "instruction": f"Gather relevant context and data for: {goal}",
                },
                {
                    "role": "general",
                    "name": "Execution Worker",
                    "instruction": f"Execute implementation tasks for: {goal}",
                },
            ]

        launched_tasks: List[SwarmTask] = []
        for item in subtasks_data[:max_workers]:
            task = await self.spawn_worker(
                role=item.get("role", "general"),
                instruction=item.get("instruction", goal),
                name=item.get("name", ""),
                parent_goal=goal,
                client=client,
            )
            launched_tasks.append(task)

        return launched_tasks

    async def synthesize_swarm_results(
        self,
        parent_goal: str,
        tasks: List[SwarmTask],
        client: Optional[LLMClient] = None,
    ) -> str:
        """Synthesize multiple completed sub-agent tasks into a unified briefing."""
        llm = client or LLMClient.from_settings()
        task_summaries = []
        for t in tasks:
            task_summaries.append(f"### Worker: {t.name} ({t.role.value})\nStatus: {t.status.value}\nOutput:\n{t.result or t.error or 'No output'}")

        prompt = (
            f"Synthesize the following sub-agent swarm worker findings for the primary goal: '{parent_goal}'.\n\n"
            + "\n\n".join(task_summaries)
            + "\n\nProvide an executive summary synthesizing the key findings and actions taken."
        )

        try:
            resp = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
            )
            return (resp.reply if hasattr(resp, "reply") else str(resp)).strip()
        except Exception:
            return "\n\n".join(task_summaries)


def get_swarm_engine(
    store: Optional[SwarmStore] = None,
    registry: Optional[ToolRegistry] = None,
    executor: Optional[Any] = None,
    max_concurrent_workers: int = 5,
) -> SwarmEngine:
    """Get or create singleton instance of SwarmEngine."""
    global _SWARM_ENGINE_SINGLETON
    if _SWARM_ENGINE_SINGLETON is None:
        _SWARM_ENGINE_SINGLETON = SwarmEngine(
            store=store,
            registry=registry,
            executor=executor,
            max_concurrent_workers=max_concurrent_workers,
        )
    elif executor is not None:
        _SWARM_ENGINE_SINGLETON.executor = executor
    return _SWARM_ENGINE_SINGLETON

