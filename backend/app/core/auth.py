import hmac

from fastapi import Header, HTTPException

from app.core.config import settings


async def require_access_token(x_access_token: str | None = Header(default=None)) -> None:
    """Gates a route behind `settings.access_token`. If no token is
    configured (local development), every request is let through.
    """
    if not settings.access_token:
        return
    if x_access_token is None or not hmac.compare_digest(x_access_token, settings.access_token):
        raise HTTPException(status_code=401, detail="Missing or invalid access token")
