"""API authentication middleware for Evidence Library write operations."""

import logging
from fastapi import HTTPException, Request, status
from ornery_kiwi.config import API_TOKEN

logger = logging.getLogger(__name__)


def check_write_token(request: Request):
    """
    Dependency to check API_TOKEN for write operations.
    Raises 403 if token is required but missing/invalid.
    If no API_TOKEN is configured, skips auth (localhost-only mode).
    """
    if not API_TOKEN:
        # No token configured — allow (localhost-only security model)
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Use: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.split(" ", 1)[1]
    if token != API_TOKEN:
        logger.warning(f"Failed auth attempt from {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API token",
        )
