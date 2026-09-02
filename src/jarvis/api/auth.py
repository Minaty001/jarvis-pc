from fastapi import Header, HTTPException, status
from jarvis.config.settings import get_settings


def verify_auth(authorization: str | None = Header(None)) -> None:
    settings = get_settings()
    is_remote = settings.host not in ("127.0.0.1", "localhost", "::1")
    if not settings.api_token:
        if settings.environment == "production" or is_remote:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JARVIS_API_TOKEN is mandatory in production or remote host environment",
            )
        return
    if authorization != f"Bearer {settings.api_token}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
        )

