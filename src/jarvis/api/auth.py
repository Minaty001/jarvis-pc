from fastapi import Header, HTTPException, status
from jarvis.config.settings import get_settings


def verify_auth(authorization: str | None = Header(None)) -> None:
    settings = get_settings()
    if not settings.api_token:
        return
    if authorization != f"Bearer {settings.api_token}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
        )
