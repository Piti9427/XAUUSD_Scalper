"""Webhook Bearer / X-Webhook-Secret auth dependency factory."""

from __future__ import annotations

import hmac
from typing import Callable, Optional

from fastapi import Header, HTTPException, status

# SEC-17 (2026-11-13): these values were hardcoded fallbacks and are in git history. Treat as burned.
BURNED_SECRETS = frozenset({"XAUUSD_DEFAULT_SECRET", "DEV_SECRET_123", "XAUUSD_MASTER_SECRET_2026"})


def require_usable_secret(token: Optional[str]) -> str:
    """Fail closed: no empty, whitespace-only or burned webhook secret."""
    if not isinstance(token, str) or not token.strip():
        raise ValueError("webhook_secret_required")
    if token.strip() in BURNED_SECRETS:
        raise ValueError("webhook_secret_burned")
    return token


def resolve_webhook_secret(env_value: Optional[str], config_value: Optional[str]) -> str:
    """Env WEBHOOK_SECRET first, then config; never a hardcoded default. Exit if unusable."""
    try:
        return require_usable_secret(env_value or config_value)
    except ValueError as error:
        raise SystemExit(f"{error}: set WEBHOOK_SECRET (or webhook.secret_token) to a fresh secret") from None


def make_verify_auth(auth_token: str) -> Callable:
    """Return FastAPI dependency that validates webhook auth headers."""
    expected = require_usable_secret(auth_token).encode()

    async def verify_auth(
        authorization: Optional[str] = Header(None),
        x_webhook_secret: Optional[str] = Header(None),
    ):
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[len("Bearer ") :].strip()
        elif x_webhook_secret:
            token = x_webhook_secret.strip()

        if not token or not hmac.compare_digest(token.encode(), expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing authorization token",
            )
        return True

    return verify_auth
