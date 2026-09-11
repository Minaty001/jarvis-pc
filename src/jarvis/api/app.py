from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from jarvis.api.auth import verify_auth
from jarvis.api.schemas import ChatRequest, ChatResponse, ExecuteRequest, ExecuteResponse
from jarvis.tools.executor import ConfirmationRequired, ToolDenied, ToolExecutor
from jarvis.tools.rate_limit import RateLimitExceeded
from jarvis.cognitive.context import ExecutionContext

import uuid


def create_api_app(executor: ToolExecutor, agent=None) -> FastAPI:
    """Factory: create FastAPI app with injected executor."""
    chat_agent = agent
    api = FastAPI(title="JARVIS API", version="1.0.0")

    @api.middleware("http")
    async def limit_request_body(request: Request, call_next):
        from jarvis.config.settings import get_settings
        settings = get_settings()
        cl = request.headers.get("content-length")
        if cl and int(cl) > settings.max_request_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                content={"detail": f"Request body exceeds {settings.max_request_bytes} bytes"},
            )
        return await call_next(request)

    @api.exception_handler(ToolDenied)
    async def tool_denied_handler(request: Request, exc: ToolDenied):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    @api.exception_handler(ConfirmationRequired)
    async def confirmation_required_handler(request: Request, exc: ConfirmationRequired):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @api.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": str(exc)})

    @api.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})

    @api.get("/health")
    async def health():
        return {"status": "ok"}

    @api.post("/execute", response_model=ExecuteResponse)
    async def execute(request: ExecuteRequest, _: None = Depends(verify_auth)):
        ctx = ExecutionContext(
            session_id="api",
            task_id=f"api-{uuid.uuid4().hex[:8]}",
            user_id="api-user",
            request_id=str(uuid.uuid4()),
            permissions=frozenset({"filesystem.read", "system.read", "network.read"}),
        )
        try:
            result = await executor.execute(
                request.tool,
                context=ctx,
                confirmation_token=request.confirmation_token,
                arguments=request.arguments,
            )
            return ExecuteResponse(ok=True, result=result)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown tool: {request.tool}") from exc

    @api.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest, _: None = Depends(verify_auth)):
        from jarvis.brain.agent import build_agent

        nonlocal chat_agent
        if chat_agent is None:
            chat_agent = build_agent(executor)
        try:
            reply = await chat_agent.respond(request.message, session_id=request.session_id)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"brain failure: {exc}",
            ) from exc
        return ChatResponse(reply=reply)

    return api
