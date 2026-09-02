from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from jarvis.api.auth import verify_auth
from jarvis.api.schemas import ExecuteRequest, ExecuteResponse
from jarvis.tools.executor import ConfirmationRequired, ToolDenied, ToolExecutor
from jarvis.tools.rate_limit import RateLimitExceeded

app = FastAPI(title="JARVIS API", version="1.0.0")
_tool_executor = ToolExecutor()


def get_tool_executor() -> ToolExecutor:
    return _tool_executor


@app.exception_handler(ToolDenied)
async def tool_denied_handler(request: Request, exc: ToolDenied):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
    )


@app.exception_handler(ConfirmationRequired)
async def confirmation_required_handler(request: Request, exc: ConfirmationRequired):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": str(exc)},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/execute", response_model=ExecuteResponse)
async def execute(
    request: ExecuteRequest,
    _: None = Depends(verify_auth),
):
    try:
        executor = get_tool_executor()
        result = await executor.execute(
            request.tool,
            confirmation_token=request.confirmation_token,
            arguments=request.arguments,
        )
        return ExecuteResponse(ok=True, result=result)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown tool: {request.tool}",
        ) from exc
