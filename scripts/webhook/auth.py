"""Webhook Bearer / X-Webhook-Secret auth dependency factory."""

from __future__ import annotations

from typing import Callable, Optional

from fastapi import Header, HTTPException, status


def make_verify_auth(auth_token: str) -> Callable:
    """Return FastAPI dependency that validates webhook auth headers."""

    async def verify_auth(
        authorization: Optional[str] = Header(None),
        x_webhook_secret: Optional[str] = Header(None),
    ):
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[len("Bearer ") :].strip()
        elif x_webhook_secret:
            token = x_webhook_secret.strip()

        if not token or token != auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing authorization token",
            )
        return True

    return verify_auth
