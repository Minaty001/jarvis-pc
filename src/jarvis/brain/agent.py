"""The JARVIS brain: a ReAct agent loop over the live tool registry.

Perceive (user input + memory) -> Reason (LLM) -> Act (ToolExecutor,
guardrails intact) -> Observe (results fed back) -> repeat until satisfied.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Awaitable, Callable

from jarvis.brain.client import ChatResult, LLMClient
from jarvis.brain.goals import plan_goal, reflect_goal, verify_goal
from jarvis.brain.memory import MemoryStore
from jarvis.brain.persona import build_system_prompt
from jarvis.cognitive.context import ExecutionContext
from jarvis.tasks.store import TaskStore
from jarvis.tools.executor import ConfirmationRequired, ToolExecutor
from jarvis.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

MAX_STEPS = 8
MAX_REPLANS = 2

# Static argument schemas for the tools the LLM may call. Only tools with a
# spec here are exposed to the model — a tool without a schema stays unreachable.
TOOL_SPECS: dict[str, dict[str, Any]] = {
    "read_file": {
        "description": "Read the contents of a text file within the allowed home directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_path": {"type": "string", "description": "Path to the file, absolute or relative to home."},
                "encoding": {"type": "string", "description": "File encoding, default utf-8."},
            },
            "required": ["user_path"],
        },
    },
    "write_file": {
        "description": "Write content to a file within the allowed home directory. Requires confirmation.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_path": {"type": "string", "description": "Path to the file, absolute or relative to home."},
                "content": {"type": "string", "description": "Full file contents to write."},
            },
            "required": ["user_path", "content"],
        },
    },
    "open_application": {
        "description": "Launch a allowed desktop application (firefox, chrome, terminal). Requires confirmation.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "One of: firefox, chrome, terminal."},
            },
            "required": ["name"],
        },
    },
    "open_url": {
        "description": "Open a website or search page in the default browser. Requires confirmation.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full URL to open, e.g. https://www.youtube.com/results?search_query=headlight+song"},
            },
            "required": ["url"],
        },
    },
    "find_processes": {
        "description": "Find running processes. With an exact name, returns matching pid/name/user entries; without a name, returns the total process count and a sample.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Exact process name to filter by, e.g. 'firefox'. Omit to list all."},
                "limit": {"type": "integer", "description": "Max sample entries to return when no name is given. Default 50."},
            },
        },
    },
    "check_camera": {
        "description": "Check whether the camera device is present and accessible.",
        "parameters": {
            "type": "object",
            "properties": {
                "device_path": {"type": "string", "description": "Device path, default /dev/video0."},
            },
        },
    },
    "list_cameras": {
        "description": "Discover and list all available camera/video capture hardware devices attached to the computer.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    "take_photo": {
        "description": "Capture a photo from a connected camera device. Requires confirmation. Saves to user's Pictures directory or specified path.",
        "parameters": {
            "type": "object",
            "properties": {
                "output_path": {"type": "string", "description": "Destination file path within home directory (e.g. ~/Pictures/photo.jpg). Optional."},
                "device_path": {"type": "string", "description": "Camera device path, default /dev/video0."},
            },
        },
    },
    "play_song": {
        "description": "Find and open the top YouTube result for a song or music request, ready to play. Requires confirmation.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The song or search terms, e.g. 'headlights song'."},
            },
            "required": ["query"],
        },
    },
    "browse_web": {
        "description": "Fetch a web page headlessly and return its rendered visible text and title. Enables reading pages, lookups, and research without opening a window.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full http(s) URL to fetch and read."},
            },
            "required": ["url"],
        },
    },
}


def _tool_schemas(registry: ToolRegistry) -> list[dict]:
    schemas: list[dict] = []
    for tool in registry.list():
        spec = TOOL_SPECS.get(tool.name)
        if spec is None:
            continue
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": spec["description"],
                    "parameters": spec["parameters"],
                },
            }
        )
    return schemas


def _tools_brief(schemas: list[dict]) -> str:
    lines = []
    for schema in schemas:
        fn = schema["function"]
        lines.append(f"- {fn['name']}({', '.join(fn['parameters'].get('properties', {}))})")
    return "\n".join(lines)


ConfirmationResolved = Awaitable[str | None]
ConfirmationResolver = Callable[[str, dict[str, Any]], ConfirmationResolved]


class JarvisAgent:
    """ReAct agent: reasons with an LLM and acts through the tool executor."""

    def __init__(
        self,
        executor: ToolExecutor,
        client: LLMClient | None = None,
        memory: MemoryStore | None = None,
        confirmation_secret: str | None = None,
        confirmation_resolver: ConfirmationResolver | None = None,
        max_steps: int = MAX_STEPS,
        task_store: TaskStore | None = None,
    ) -> None:
        self.executor = executor
        self.client = client or LLMClient.from_settings()
        self.memory = memory
        self.confirmation_secret = confirmation_secret
        self.confirmation_resolver = confirmation_resolver
        self.max_steps = max_steps
        self.task_store = task_store
        self._permissions = frozenset(
            cap for tool in executor.registry.list() for cap in tool.capabilities
        )

    def _context(self, session_id: str, request_id: str) -> ExecutionContext:
        return ExecutionContext(
            session_id=session_id,
            task_id=f"brain-{uuid.uuid4().hex[:8]}",
            user_id="operator",
            request_id=request_id,
            permissions=self._permissions,
        )

    async def _run_tool_call(self, call, context: ExecutionContext) -> str:
        tool = self.executor.registry.get(call.name)
        if tool is None:
            return f"observation: unknown tool '{call.name}'."
        try:
            result = await self.executor.execute(
                call.name, context=context, arguments=call.arguments
            )
            return f"observation ({call.name}): {result}"
        except ConfirmationRequired:
            token: str | None = None
            if self.confirmation_resolver is not None:
                token = await self.confirmation_resolver(call.name, call.arguments)
            if token and self.confirmation_secret:
                try:
                    result = await self.executor.execute(
                        call.name,
                        context=context,
                        arguments=call.arguments,
                        confirmation_token=token,
                        secret=self.confirmation_secret,
                    )
                    return f"observation ({call.name}): {result}"
                except Exception as exc:
                    return f"observation ({call.name}): tool failed: {exc}"
            return f"observation ({call.name}): approval required and was not granted."
        except Exception as exc:
            return f"observation ({call.name}): tool failed: {exc}"

    async def respond(self, user_text: str, session_id: str | None = None) -> str:
        session_id = session_id or "default"
        request_id = uuid.uuid4().hex

        # Resume from persisted transcript when this session has run before.
        if self.task_store is not None:
            self.task_store.create(task_id=session_id, goal=user_text)
            stored = self.task_store.get(session_id)
            stored_transcript = stored["transcript"] if stored else []
            self.task_store.set_status(session_id, "running")
        else:
            stored_transcript = []

        schemas = _tool_schemas(self.executor.registry)
        memories = self.memory.recall(user_text) if self.memory else None

        system = build_system_prompt(
            memories="\n".join(memories) if memories else None,
            tools=_tools_brief(schemas),
        )
        messages: list[dict] = [
            {"role": "system", "content": system},
            *stored_transcript,
            {"role": "user", "content": user_text},
        ]

        context = self._context(session_id, request_id)
        final_content: str | None = None

        for _ in range(self.max_steps):
            try:
                result: ChatResult = await self.client.chat(messages, tools=schemas or None)
            except Exception as exc:
                logger.warning("LLM call failed: %s", exc)
                final_content = "I appear to have lost contact with my reasoning core, sir."
                break

            if result.content:
                final_content = result.content

            if not result.tool_calls:
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": result.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.name, "arguments": _dump_json(call.arguments)},
                        }
                        for call in result.tool_calls
                    ],
                }
            )
            for call in result.tool_calls:
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": await self._run_tool_call(call, context)}
                )
        else:
            if final_content is None:
                final_content = "I have exhausted my step budget without reaching a clean answer, sir."

        final_content = "Understood. Anything else, sir." if final_content is None else final_content
        reply = final_content
        if self.task_store is not None:
            self.task_store.set_transcript(session_id, messages[1:] + [{"role": "assistant", "content": reply}])
            self.task_store.set_status(session_id, "completed")
        if self.memory:
            self.memory.add(user_text, reply)
        return reply

    async def run_goal(self, goal: str, session_id: str | None = None) -> str:
        """Plan a goal, execute it through the ReAct loop, verify, and re-plan until
        the verifier is satisfied (bounded by MAX_REPLANS)."""
        session_id = session_id or f"goal-{uuid.uuid4().hex[:8]}"
        if self.task_store is not None:
            self.task_store.create(task_id=session_id, goal=goal)

        feedback = ""
        met = False
        transcript: list[dict] = []
        reply = ""
        for attempt in range(MAX_REPLANS + 1):
            plan = await plan_goal(self.client, goal, memory=self.memory)
            if self.task_store is not None:
                self.task_store.set_plan(session_id, plan)
                self.task_store.set_status(session_id, "running")

            prompt = goal if not feedback else f"{goal}\n\nRe-attempt {attempt}. Prior verification:\n{feedback}"
            reply = await self.respond(prompt, session_id=session_id)

            if self.task_store is not None:
                stored = self.task_store.get(session_id)
                transcript = stored["transcript"] if stored else []
            else:
                transcript = [{"role": "user", "content": prompt}, {"role": "assistant", "content": reply}]
            met, feedback = await verify_goal(self.client, goal, transcript)
            if met:
                if self.task_store is not None:
                    self.task_store.set_status(session_id, "completed")
                break
        else:
            if self.task_store is not None:
                self.task_store.set_status(session_id, "failed")

        if self.memory is not None:
            from jarvis.brain.reflection import ReflectionEngine

            engine = ReflectionEngine(llm_client=self.client)
            reflection = await engine.reflect_on_outcome(
                goal=goal,
                plan=plan if "plan" in locals() else [],
                transcript=[m.get("content", "") for m in transcript if isinstance(m, dict)],
                verified=met,
                error=None if met else feedback,
            )
            lesson_text = reflection.get("lesson")
            if lesson_text:
                self.memory.add(f"LESSON: {goal}", f"OUTCOME: {'achieved' if met else 'not achieved'} | {lesson_text}")
                if hasattr(self.memory, "store_reflection"):
                    self.memory.store_reflection(
                        goal_query=goal,
                        lesson=lesson_text,
                        category=reflection.get("category", "general"),
                        recipe=reflection.get("recipe"),
                        verified=met,
                    )

        return reply


def _dump_json(value: dict[str, Any]) -> str:
    import json as _json

    return _json.dumps(value, default=str)


def build_agent(
    executor: ToolExecutor,
    confirmation_secret: str | None = None,
    memory_path: str | None = None,
    task_store: TaskStore | None = None,
) -> JarvisAgent:
    """Construct a JarvisAgent wired to the given executor and optional storage."""
    from jarvis.system.paths import get_app_paths

    if memory_path is None:
        memory_path = get_app_paths().state / "memory.db"
    if task_store is None:
        task_store = TaskStore(get_app_paths().state / "tasks.db")
    return JarvisAgent(
        executor=executor,
        client=LLMClient.from_settings(),
        memory=MemoryStore(memory_path),
        confirmation_secret=confirmation_secret,
        task_store=task_store,
    )