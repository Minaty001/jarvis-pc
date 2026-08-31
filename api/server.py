"""
REST API — HTTP interface to the cognitive engine with Web UI.
Serves static files, SSE for real-time updates, and full CRUD endpoints.
"""

import asyncio
import json
import time
import queue
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Optional
from threading import Thread
from urllib.parse import urlparse, parse_qs

from config.logger import get_logger
from core.observability import metrics

logger = get_logger("api.server")

WEBAPP_DIR = Path(__file__).parent.parent / "webapp"

MIME_TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

# SSE client management
_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()


def broadcast_sse(event_type: str, data: dict):
    """Broadcast an SSE event to all connected clients."""
    msg = f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


class JarvisAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the JARVIS API with Web UI."""

    engine: Any = None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        routes = {
            "/api/health": self._handle_health,
            "/api/status": self._handle_status,
            "/api/metrics": self._handle_metrics,
            "/api/memory": self._handle_memory,
            "/api/memory/working": lambda: self._handle_memory_type("working"),
            "/api/memory/episodic": lambda: self._handle_memory_type("episodic"),
            "/api/memory/semantic": lambda: self._handle_memory_type("semantic"),
            "/api/memory/procedural": lambda: self._handle_memory_type("procedural"),
            "/api/memory/preference": lambda: self._handle_memory_type("preference"),
            "/api/memory/failure": lambda: self._handle_memory_type("failure"),
            "/api/conversations": self._handle_conversations,
            "/api/tasks": self._handle_tasks,
            "/api/tools": self._handle_tools,
            "/api/system": self._handle_system,
            "/api/events": self._handle_events,
            "/health": self._handle_health,
            "/status": self._handle_status,
            "/metrics": self._handle_metrics,
            "/memory": self._handle_memory,
            "/tasks": self._handle_tasks,
            "/tools": self._handle_tools,
        }

        if path in routes:
            handler = routes[path]
            if callable(handler):
                handler()
            else:
                handler()
        elif path == "/api/events/stream" or path == "/events/stream":
            self._handle_sse()
        elif path == "/" or path == "/index.html":
            self._serve_file("index.html")
        else:
            self._serve_static(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/chat", "/api/chat"):
            self._handle_chat()
        elif path in ("/execute", "/api/execute"):
            self._handle_execute()
        elif path in ("/memory", "/api/memory"):
            self._handle_memory_add()
        elif path == "/api/conversations":
            self._handle_conversations_add()
        else:
            self._handle_404()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/conversations/"):
            conv_id = path.split("/")[-1]
            self._handle_conversation_delete(conv_id)
        elif path.startswith("/api/memory/"):
            parts = path.split("/")
            if len(parts) >= 4:
                mem_type = parts[2]
                mem_id = parts[3]
                self._handle_memory_delete(mem_type, mem_id)
            else:
                self._handle_404()
        else:
            self._handle_404()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── Health & Status ──

    def _handle_health(self):
        self._json_response(200, {"status": "healthy", "timestamp": time.time()})

    def _handle_status(self):
        if not self.engine:
            self._json_response(503, {"error": "Engine not initialized"})
            return
        try:
            snapshot = self.engine.world_state.snapshot() if hasattr(self.engine, 'world_state') else {}
            bus_stats = {}
            if hasattr(self.engine, 'event_bus') and self.engine.event_bus:
                bus_stats = self.engine.event_bus.stats if hasattr(self.engine.event_bus, 'stats') else {}
            self._json_response(200, {
                "world_state": snapshot,
                "event_bus": bus_stats,
                "metrics": metrics.snapshot(),
            })
        except Exception:
            self._json_response(200, {
                "world_state": {"task_status": "idle"},
                "event_bus": {},
                "metrics": metrics.snapshot(),
            })

    def _handle_metrics(self):
        self._json_response(200, metrics.snapshot())

    def _handle_system(self):
        """System metrics from SystemMonitor."""
        try:
            from perception.system_monitor import system_monitor
            snapshot = system_monitor.get_snapshot()
            self._json_response(200, snapshot)
        except Exception as e:
            self._json_response(200, {"error": str(e)})

    def _handle_events(self):
        """Recent events from EventBus."""
        try:
            from perception.event_bus import event_bus
            # EventBus doesn't store recent events list, return empty for now
            # Could be enhanced by adding event history tracking to EventBus
            recent = []
            self._json_response(200, {"events": recent[-50:]})
        except Exception as e:
            self._json_response(200, {"events": [], "error": str(e)})

    # ── SSE ──

    def _handle_sse(self):
        """Server-Sent Events endpoint for real-time updates."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        q = queue.Queue(maxsize=100)
        with _sse_lock:
            _sse_clients.append(q)

        try:
            while True:
                try:
                    msg = q.get(timeout=15)
                    self.wfile.write(msg.encode())
                    self.wfile.flush()
                except queue.Empty:
                    # Send keepalive comment
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    # ── Memory ──

    def _handle_memory(self):
        try:
            from memory.memory_manager import memory_manager
            self._json_response(200, {"summary": memory_manager.summarize_all()})
        except Exception as e:
            self._json_response(200, {"summary": f"Memory system: {e}"})

    def _handle_memory_type(self, mem_type: str):
        """Return entries for a specific memory type."""
        try:
            from memory import (
                working_memory, episodic_memory, semantic_memory,
                procedural_memory, preference_memory, failure_memory,
            )
            stores = {
                "working": working_memory,
                "episodic": episodic_memory,
                "semantic": semantic_memory,
                "procedural": procedural_memory,
                "preference": preference_memory,
                "failure": failure_memory,
            }
            store = stores.get(mem_type)
            if not store:
                self._json_response(400, {"error": f"Unknown memory type: {mem_type}"})
                return

            entries = []
            if mem_type == "working":
                for k, v in store.all().items():
                    entries.append({"key": k, "value": v})
            elif mem_type == "preference":
                for p in store.retrieve(limit=100):
                    entries.append({
                        "id": p.get("id", ""), "key": p.get("key", ""),
                        "value": p.get("value", ""), "category": p.get("category", ""),
                    })
            elif hasattr(store, '_store'):
                entries = store._store[-50:] if isinstance(store._store, list) else []

            self._json_response(200, {"type": mem_type, "entries": entries, "count": len(entries)})
        except Exception as e:
            self._json_response(200, {"type": mem_type, "entries": [], "error": str(e)})

    def _handle_memory_add(self):
        """Add a memory entry."""
        try:
            body = self._read_body()
            content = body.get("content", "")
            mem_type = body.get("type", "working")
            metadata = body.get("metadata", {})
            from memory.memory_manager import memory_manager
            entry_id = memory_manager.remember(content, mem_type, metadata)
            self._json_response(200, {"success": True, "id": entry_id})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    def _handle_memory_delete(self, mem_type: str, entry_id: str):
        """Delete a memory entry."""
        try:
            from memory import working_memory, preference_memory
            if mem_type == "working":
                working_memory.delete(entry_id)
            elif mem_type == "preference":
                preference_memory.delete(entry_id)
            self._json_response(200, {"success": True})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    # ── Conversations ──

    def _handle_conversations(self):
        """List recent conversations."""
        try:
            from memory.conversation import conversation_store
            sessions = conversation_store.sessions() if hasattr(conversation_store, 'sessions') else []
            self._json_response(200, {"sessions": sessions})
        except Exception as e:
            self._json_response(200, {"sessions": [], "error": str(e)})

    def _handle_conversations_add(self):
        """Add a conversation turn."""
        try:
            body = self._read_body()
            session_id = body.get("session_id", "default")
            role = body.get("role", "user")
            content = body.get("content", "")
            from memory.conversation import conversation_store
            if hasattr(conversation_store, 'record'):
                conversation_store.record(session_id, role, content)
            self._json_response(200, {"success": True})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    def _handle_conversation_delete(self, conv_id: str):
        """Delete a conversation."""
        try:
            from memory.conversation import conversation_store
            if hasattr(conversation_store, 'clear_session'):
                conversation_store.clear_session(conv_id)
            self._json_response(200, {"success": True})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    # ── Tasks ──

    def _handle_tasks(self):
        try:
            from planning.task_state import task_store
            active = [t.to_dict() for t in task_store.get_by_status("running")]
            pending = [t.to_dict() for t in task_store.get_by_status("pending")]
            completed = [t.to_dict() for t in task_store.get_by_status("completed")]
            self._json_response(200, {
                "active": active, "pending": pending,
                "completed": completed[-20:],
            })
        except Exception as e:
            self._json_response(200, {"active": [], "pending": [], "completed": []})

    # ── Tools ──

    def _handle_tools(self):
        try:
            from tools.registry import tool_registry
            tools = []
            for t in tool_registry.list_tools():
                tools.append({
                    "name": t.name,
                    "description": t.description,
                    "category": t.category.value,
                    "risk": t.risk_level.value,
                    "parameters": t.parameters,
                    "requires_confirmation": t.requires_confirmation,
                })
            stats = tool_registry.get_call_stats()
            self._json_response(200, {"tools": tools, "stats": stats})
        except Exception as e:
            self._json_response(200, {"tools": [], "stats": {}})

    # ── Chat ──

    def _handle_chat(self):
        try:
            body = self._read_body()
            message = body.get("message", "")
            if not message:
                self._json_response(400, {"error": "No message provided"})
                return

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self._process_chat(message))
            loop.close()
            # Return both keys for compatibility with all clients
            self._json_response(200, {
                "response_text": result,
                "result": result,
                "response": result,
            })
        except Exception as e:
            logger.error("Chat error: %s", e)
            self._json_response(500, {"error": str(e)})

    async def _process_chat(self, message: str) -> str:
        if self.engine and hasattr(self.engine, 'process_goal'):
            result = await self.engine.process_goal(message)
            if result.get("status") == "completed":
                exec_result = result.get("result", {})
                results = exec_result.get("results", [])
                if results:
                    last_result = results[-1]
                    if isinstance(last_result, dict):
                        r = last_result.get("result", "")
                        if r:
                            return str(r)
                duration = result.get("duration_sec", 0)
                return f"Done in {duration:.1f}s"
            return f"Task status: {result.get('status', 'unknown')}"

        try:
            from llm.gateway import llm_gateway
            response = await llm_gateway.generate(
                prompt=message,
                system_prompt=(
                    "You are JARVIS, an intelligent AI assistant for Linux desktop. "
                    "Be concise, helpful, and friendly. Respond in the same language the user uses."
                ),
                task_type="chat",
                max_tokens=1024,
            )
            return response.text
        except Exception as e:
            return f"I'm having trouble processing that request. Error: {e}"

    # ── Execute ──

    def _handle_execute(self):
        try:
            body = self._read_body()
            tool_name = body.get("tool", "")
            args = body.get("args", {})
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self._execute_tool(tool_name, args))
            loop.close()
            self._json_response(200, result)
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    async def _execute_tool(self, tool_name: str, args: dict) -> dict:
        try:
            from tools.executor import tool_executor
            return await tool_executor.execute(tool_name, args)
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Static files ──

    def _serve_static(self, path: str):
        file_path = WEBAPP_DIR / path.lstrip("/")
        if not file_path.exists() or not file_path.is_file():
            self._handle_404()
            return
        try:
            file_path.resolve().relative_to(WEBAPP_DIR.resolve())
        except ValueError:
            self._handle_404()
            return
        suffix = file_path.suffix.lower()
        content_type = MIME_TYPES.get(suffix, "application/octet-stream")
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self._handle_404()

    def _serve_file(self, filename: str):
        self._serve_static("/" + filename)

    # ── Helpers ──

    def _json_response(self, code: int, data: dict):
        body = json.dumps(data, indent=2, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _handle_404(self):
        self._json_response(404, {"error": "Not found"})

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length)
        return json.loads(body)

    def log_message(self, format, *args):
        logger.debug("API: %s", format % args)


class JarvisAPI:
    """HTTP API server for the cognitive engine with Web UI."""

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        import os
        self.host = host or os.environ.get("HOST", "0.0.0.0")
        self.port = port or int(os.environ.get("PORT", "3000"))
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[Thread] = None

    def start(self, engine: Any, blocking: bool = False) -> None:
        JarvisAPIHandler.engine = engine
        self._server = HTTPServer((self.host, self.port), JarvisAPIHandler)
        logger.info("API server listening on http://%s:%d", self.host, self.port)
        if blocking:
            self._server.serve_forever()
        else:
            self._thread = Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            logger.info("API server stopped")


jarvis_api = JarvisAPI()
