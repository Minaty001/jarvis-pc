"""
UIBridge — connects the JARVIS cognitive engine to the GTK UI.

Responsibilities
  * Hold references to the engine objects (orchestrator, event_bus, world_state,
    system_monitor, proactive_engine, llm_gateway).
  * Poll world_state/system_monitor on a 1 Hz timer (cheap) and push to the UI.
  * Subscribe to the async event_bus and forward structured events to the UI.
  * Register a proactive_engine callback for suggestions.
  * Send user chat to orchestrator.process_goal() (async) and stream the result.
  * Marshal everything into GTK with GLib.idle_add (UI is single-threaded).

The bridge runs the engine's asyncio loop on its OWN thread. The GTK main loop runs
on the main thread. They never share the GIL in a blocking way because all engine
calls happen on the bridge thread and results are scheduled into GTK via idle_add.
"""

import asyncio
import threading
import time

from gi.repository import GLib

from config.logger import get_logger

logger = get_logger("ui.bridge")


class UIBridge:
    def __init__(self, engine=None):
        """
        engine: an object/dict exposing the cognitive objects. We accept a duck-typed
        bundle so it can be tested with stubs. Real call wires:
            UIBridge(engine=cognitive_orchestrator)  + setters for the rest.
        Expected attrs: orchestrator, event_bus, world_state, system_monitor,
        proactive_engine, llm_gateway.
        """
        self.engine = engine
        self.orchestrator = getattr(engine, "orchestrator", None)
        self.event_bus = getattr(engine, "event_bus", None)
        self.world_state = getattr(engine, "world_state", None)
        self.system_monitor = getattr(engine, "system_monitor", None)
        self.proactive_engine = getattr(engine, "proactive_engine", None)
        self.llm_gateway = getattr(engine, "llm_gateway", None)

        self._loop = None
        self._thread = None
        self._running = False
        self._poll_id = None
        self._last_summary_time = 0.0
        self._cached_tools_txt = ""
        self._cached_mem_txt = ""

        # UI hooks (set by JarvisApp)
        self.on_orb_state = None        # (state:str) -> None
        self.on_status = None           # (text:str) -> None
        self.on_chat = None             # (role,text) -> None
        self.on_system = None           # (metrics:dict) -> None
        self.on_tools = None            # (text:str) -> None
        self.on_memory = None           # (text:str) -> None
        self.on_suggestion = None       # (text:str) -> None

    # ── lifecycle ───────────────────────────────────────────────────────
    def start(self):
        self._running = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        # subscribe to events (event_bus is async; dispatch from our loop)
        if self.event_bus:
            try:
                self.event_bus.subscribe_all(self._on_event)
            except Exception as e:
                logger.warning("Could not subscribe to event_bus: %s", e)
        # proactive suggestions
        if self.proactive_engine:
            try:
                self.proactive_engine.add_callback(self._on_proactive)
            except Exception as e:
                logger.warning("Could not register proactive callback: %s", e)
        # task_manager approval notifications
        try:
            from task_engine.manager import task_manager
            async def _notify(msg: dict):
                if msg.get("approval_id"):
                    action = msg.get("action", "action")
                    self._idle(self.on_chat, "jarvis", f"⚠️ Approval needed for '{action}' — say 'approve' or 'deny'")
            task_manager.set_notify_callback(_notify)
        except Exception as e:
            logger.warning("Could not set task_manager notify callback: %s", e)
        # 1 Hz poll for world state / system metrics
        self._poll_id = GLib.timeout_add(1000, self._poll)
        logger.info("UIBridge started")

    def stop(self):
        self._running = False
        if self._poll_id:
            GLib.source_remove(self._poll_id)
            self._poll_id = None
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("UIBridge stopped")

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    # ── polling ─────────────────────────────────────────────────────────
    def _poll(self):
        if not self._running:
            return False
        try:
            now = time.time()
            # system metrics
            if self.system_monitor:
                snap = self.system_monitor.get_snapshot()
                if snap and self.on_system:
                    self._idle(self.on_system, snap)
            # world state → orb + status
            if self.world_state:
                ws = self.world_state
                status = getattr(ws, "task_status", "idle")
                state = self._map_state(status)
                if self.on_orb_state:
                    self._idle(self.on_orb_state, state)
                goal = getattr(ws, "current_goal", "")
                if goal and self.on_status:
                    self._idle(self.on_status, f"Working: {goal[:60]}")
                # Refresh tools/memory summaries every 10 seconds (avoids 1 Hz overhead)
                if now - self._last_summary_time >= 10.0 or not self._cached_tools_txt:
                    self._cached_tools_txt = self._tools_summary()
                    self._cached_mem_txt = self._memory_summary()
                    self._last_summary_time = now

                if self.on_tools and self._cached_tools_txt:
                    self._idle(self.on_tools, self._cached_tools_txt)
                if self.on_memory and self._cached_mem_txt:
                    self._idle(self.on_memory, self._cached_mem_txt)
        except Exception as e:
            logger.debug("poll error: %s", e)
        return True

    @staticmethod
    def _map_state(task_status: str) -> str:
        m = {
            "idle": "idle",
            "planning": "thinking",
            "executing": "working",
            "verifying": "thinking",
            "blocked": "error",
        }
        return m.get(task_status, "idle")

    # ── events ──────────────────────────────────────────────────────────
    async def _on_event(self, event):
        try:
            etype = getattr(event, "type", None)
            if etype is not None:
                etype = getattr(etype, "value", str(etype))
            payload = getattr(event, "payload", {}) or {}
            # surface notable events in the chat as system lines
            if self.on_chat and etype in ("error", "tool", "memory"):
                msg = payload.get("message") or payload.get("result") or str(payload)
                if msg:
                    self._idle(self.on_chat, "system", str(msg)[:160])
        except Exception as e:
            logger.debug("event handler error: %s", e)

    def _on_proactive(self, rule_name, suggestion):
        if self.on_suggestion:
            text = f"{suggestion}" if suggestion else rule_name
            self._idle(self.on_suggestion, text)

    # ── chat (user → engine) ────────────────────────────────────────────
    def send_chat(self, text: str):
        """Send a user message to the engine and stream the reply into the UI."""
        if self.on_chat:
            self._idle(self.on_chat, "user", text)
        if self.on_orb_state:
            self._idle(self.on_orb_state, "thinking")

        if not self.orchestrator:
            async def _run_remote():
                import httpx
                from config.settings import settings
                url = f"{settings.jarvis_api_url.rstrip('/')}/chat"
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(url, json={"message": text})
                        if resp.status_code == 200:
                            data = resp.json()
                            reply = data.get("response_text") or data.get("result") or str(data)
                            if self.on_chat:
                                self._idle(self.on_chat, "jarvis", reply)
                        else:
                            if self.on_chat:
                                self._idle(self.on_chat, "jarvis", f"Render API ({resp.status_code}): {resp.text}")
                except Exception as e:
                    logger.error("Render API call failed: %s", e)
                    if self.on_chat:
                        self._idle(self.on_chat, "jarvis", f"Render API error: {e}")
                finally:
                    if self.on_orb_state:
                        self._idle(self.on_orb_state, "idle")

            asyncio.run_coroutine_threadsafe(_run_remote(), self._loop)
            return

        async def _run():
            try:
                result = await self.orchestrator.process_goal(text, session_id="ui")
                reply = self._extract_reply(result)
                if self.on_chat:
                    self._idle(self.on_chat, "jarvis", reply)
            except Exception as e:
                logger.error("chat processing failed: %s", e)
                if self.on_chat:
                    self._idle(self.on_chat, "jarvis", f"Sorry, I hit an error: {e}")
            finally:
                if self.on_orb_state:
                    self._idle(self.on_orb_state, "idle")

        fut = asyncio.run_coroutine_threadsafe(_run(), self._loop)
        # do not block the UI thread; result arrives via idle callbacks later.

    @staticmethod
    def _extract_reply(result: dict) -> str:
        if not isinstance(result, dict):
            return str(result)
        status = result.get("status")
        if status == "completed":
            results = result.get("result", {}).get("results", [])
            if results:
                outputs = []
                for step_res in results:
                    if isinstance(step_res, dict):
                        r = step_res.get("result") or step_res.get("output")
                        if r and str(r).strip():
                            outputs.append(str(r).strip())
                if outputs:
                    return "\n".join(outputs)
            return f"Task done in {result.get('duration_sec', 0):.1f}s."
        if status == "failed":
            return f"I couldn't complete that: {result.get('error', 'unknown error')}"
        return str(result)

    # ── summaries ───────────────────────────────────────────────────────
    def _tools_summary(self) -> str:
        try:
            from jarvis.tools.registry import ToolRegistry
            registry = ToolRegistry()
            tools = registry.list()
            names = [t.name for t in tools]
            if not names:
                return ""
            return ", ".join(names[:12]) + (f" ({len(names)} total)" if len(names) > 12 else "")
        except Exception:
            return ""

    def _memory_summary(self) -> str:
        try:
            from memory.memory_manager import memory_manager
            s = memory_manager.summarize_all()
            if isinstance(s, dict):
                return " | ".join(f"{k}: {v}" for k, v in s.items())
            return str(s)
        except Exception:
            return ""

    # ── helpers ─────────────────────────────────────────────────────────
    @staticmethod
    def _idle(func, *args):
        GLib.idle_add(lambda: func(*args) or False)
