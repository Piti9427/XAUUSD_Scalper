"""Webhook bridge helpers extracted from create_app monolith.

Import submodules directly (e.g. ``scripts.webhook.setup_time``) so pure
helpers do not require FastAPI at import time.
"""

from __future__ import annotations

__all__ = [
    "WebhookRuntime",
    "coalesce_h1_bias",
    "make_idempotency_helpers",
    "make_verify_auth",
    "parse_h1_bias_fields",
    "resolve_h1_bias_lazy",
]


def __getattr__(name: str):
    if name == "WebhookRuntime":
        from scripts.webhook.runtime import WebhookRuntime

        return WebhookRuntime
    if name == "make_verify_auth":
        from scripts.webhook.auth import make_verify_auth

        return make_verify_auth
    if name == "make_idempotency_helpers":
        from scripts.webhook.idempotency import make_idempotency_helpers

        return make_idempotency_helpers
    if name in {
        "coalesce_h1_bias",
        "parse_h1_bias_fields",
        "resolve_h1_bias_lazy",
    }:
        from scripts.webhook import h1_bias

        return getattr(h1_bias, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
