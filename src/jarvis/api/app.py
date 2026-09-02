from fastapi import Depends, FastAPI, HTTPException
from jarvis.api.auth import verify_auth
from jarvis.api.schemas import ExecuteRequest, ExecuteResponse
from jarvis.tools.executor import ConfirmationRequired, ToolDenied, ToolExecutor

app = FastAPI(title="JARVIS API", version="1.0.0")
_tool_executor = ToolExecutor()


def get_tool_executor() -> ToolExecutor:
    return _tool_executor


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
            confirmed=request.confirmed,
            **request.arguments,
        )
        return ExecuteResponse(ok=True, result=result)
    except KeyError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"unknown tool: {request.tool}",
        ) from exc
    except (ToolDenied, ConfirmationRequired, Exception) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
