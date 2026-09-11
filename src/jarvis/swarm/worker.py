"""Sub-Agent Worker execution loop for autonomous background task completion."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from jarvis.brain.client import ChatResult, LLMClient
from jarvis.cognitive.context import ExecutionContext
from jarvis.swarm.models import SwarmTask, TaskStatus, WorkerRole
from jarvis.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Scoped tool capabilities by role
_ROLE_CAPABILITIES: Dict[WorkerRole, List[str]] = {
    WorkerRole.RESEARCHER: [
        "deep_web_research",
        "fetch_topic_news",
        "extract_web_article",
        "search_knowledge",
    ],
    WorkerRole.CODER: [
        "read_file",
        "write_file",
        "list_directory",
        "execute_code",
        "search_knowledge",
    ],
    WorkerRole.SYSTEM: [
        "get_system_health",
        "list_system_processes",
        "get_battery_status",
        "get_audio_volume",
        "get_screen_brightness",
    ],
    WorkerRole.WRITER: [
        "read_file",
        "write_file",
        "search_knowledge",
    ],
    WorkerRole.GENERAL: [],  # All registered tools
}

_ROLE_SYSTEM_PROMPTS: Dict[WorkerRole, str] = {
    WorkerRole.RESEARCHER: (
        "You are an expert autonomous Research Sub-Agent for JARVIS PC. "
        "Your task is to gather accurate, comprehensive, and up-to-date facts using web research tools. "
        "Summarize findings clearly with citations and source URLs."
    ),
    WorkerRole.CODER: (
        "You are an expert autonomous Software Engineering Sub-Agent for JARVIS PC. "
        "Your task is to analyze code, write robust implementations, and verify file operations. "
        "Provide production-ready, clean, well-documented code."
    ),
    WorkerRole.SYSTEM: (
        "You are an expert Systems & Diagnostics Sub-Agent for JARVIS PC. "
        "Your task is to monitor, inspect, and report on Linux hardware, system metrics, processes, and controls."
    ),
    WorkerRole.WRITER: (
        "You are a Technical Writer & Documentarian Sub-Agent for JARVIS PC. "
        "Your task is to compose structured, coherent, high-quality documentation, reports, and summaries."
    ),
    WorkerRole.GENERAL: (
        "You are an Autonomous Background Worker Sub-Agent for JARVIS PC. "
        "Execute the assigned instruction efficiently using available tools."
    ),
}


class SubAgentWorker:
    """Runs a single background sub-agent worker task to completion."""

    def __init__(
        self,
        task: SwarmTask,
        client: Optional[LLMClient] = None,
        registry: Optional[ToolRegistry] = None,
        executor: Optional[Any] = None,
        on_progress: Optional[Callable[[SwarmTask], None]] = None,
    ) -> None:
        self.task = task
        self.client = client
        self.registry = registry or ToolRegistry()
        self._executor = executor  # Injected from Application / SwarmEngine
        self.on_progress = on_progress
        self._cancelled = False

    def log(self, message: str, level: str = "INFO") -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "level": level,
        }
        self.task.logs.append(entry)
        logger.debug("[%s] %s", self.task.id, message)
        if self.on_progress:
            self.on_progress(self.task)

    def cancel(self) -> None:
        self._cancelled = True
        self.task.status = TaskStatus.CANCELLED
        self.task.completed_at = datetime.now(timezone.utc).isoformat()
        self.log("Worker task was cancelled by user/operator.", level="WARNING")

    def _get_scoped_tools(self) -> List[Any]:
        allowed_names = _ROLE_CAPABILITIES.get(self.task.role, [])
        if not allowed_names:
            return self.registry.list()
        return [t for t in self.registry.list() if t.name in allowed_names]

    async def _execute_tool(self, tool_name: str, args: dict, ctx: ExecutionContext) -> Any:
        if self._executor is not None:
            return await self._executor.execute(tool_name, context=ctx, arguments=args)
        t_def = self.registry.get(tool_name)
        if not t_def:
            raise KeyError(f"Tool '{tool_name}' not found.")
        fn = getattr(t_def, "handler", None)
        if not fn:
            raise ValueError(f"No handler for tool '{tool_name}'.")
        if asyncio.iscoroutinefunction(fn):
            return await fn(ctx, **args)
        return fn(ctx, **args)

    async def run(self) -> SwarmTask:
        """Execute the subagent task lifecycle."""
        self.task.status = TaskStatus.RUNNING
        self.task.started_at = datetime.now(timezone.utc).isoformat()
        self.task.progress_percent = 10
        self.log(f"Worker started task [{self.task.name or self.task.id}] with role: {self.task.role.value}")

        # Collect all capability tags from scoped tools to pass as permissions
        scoped_tools = self._get_scoped_tools()
        all_caps: set = set()
        for t in scoped_tools:
            all_caps.update(t.capabilities or set())
        swarm_permissions = frozenset(all_caps)

        try:
            client = self.client or LLMClient.from_settings()
            role_prompt = _ROLE_SYSTEM_PROMPTS.get(self.task.role, _ROLE_SYSTEM_PROMPTS[WorkerRole.GENERAL])
            system_prompt = f"{role_prompt}\n\nTask Goal: {self.task.instruction}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self.task.instruction},
            ]

            max_steps = 5
            for step in range(max_steps):
                if self._cancelled:
                    return self.task

                self.task.progress_percent = min(20 + step * 15, 85)
                self.log(f"Executing step {step + 1}/{max_steps}...")

                try:
                    # Request next turn from LLM client
                    chat_res = await client.chat(messages=messages)
                    reply_text = chat_res.reply if hasattr(chat_res, "reply") else (chat_res.get("reply", "") if isinstance(chat_res, dict) else str(chat_res))
                    tool_calls = getattr(chat_res, "tool_calls", [])

                    # Build swarm execution context with scoped permissions
                    ctx = ExecutionContext(
                        session_id="swarm",
                        task_id=self.task.id,
                        user_id="operator",
                        request_id=f"req-{step}",
                        permissions=swarm_permissions,
                    )

                    # Check structured tool calls
                    if tool_calls:
                        for tc in tool_calls:
                            tool_name = tc.name
                            tool_args = tc.args
                            self.log(f"Invoking tool: {tool_name} with args: {tool_args}")
                            try:
                                tool_result = await self._execute_tool(tool_name, tool_args, ctx)
                                messages.append({"role": "assistant", "content": reply_text or f"Tool call: {tool_name}"})
                                messages.append({"role": "system", "content": f"Tool '{tool_name}' output: {json.dumps(tool_result)}"})
                            except Exception as te:
                                messages.append({"role": "system", "content": f"Tool '{tool_name}' error: {te}"})
                    elif "```json" in reply_text and '"tool"' in reply_text:
                        # Fallback for text JSON tool calls
                        raw_json = reply_text.split("```json")[1].split("```")[0].strip()
                        tool_call = json.loads(raw_json)
                        tool_name = tool_call.get("tool", "")
                        tool_args = tool_call.get("args", {})

                        self.log(f"Invoking tool: {tool_name} with args: {tool_args}")
                        try:
                            tool_result = await self._execute_tool(tool_name, tool_args, ctx)
                            messages.append({"role": "assistant", "content": reply_text})
                            messages.append({"role": "system", "content": f"Tool '{tool_name}' output: {json.dumps(tool_result)}"})
                        except Exception as te:
                            messages.append({"role": "system", "content": f"Tool '{tool_name}' error: {te}"})
                    else:
                        # Direct answer completed
                        self.task.result = reply_text.strip()
                        break

                except Exception as exc:
                    self.log(f"Turn {step + 1} exception: {exc}", level="WARNING")
                    if not self.task.result:
                        self.task.result = f"Worker processed task: {self.task.instruction}"
                    break

            if not self.task.result:
                self.task.result = f"Task completed successfully for instruction: {self.task.instruction}"

            self.task.status = TaskStatus.COMPLETED
            self.task.progress_percent = 100
            self.task.completed_at = datetime.now(timezone.utc).isoformat()
            self.log("Worker finished task successfully.")

        except Exception as err:
            self.task.status = TaskStatus.FAILED
            self.task.error = str(err)
            self.task.completed_at = datetime.now(timezone.utc).isoformat()
            self.log(f"Worker failed with error: {err}", level="ERROR")

        return self.task

