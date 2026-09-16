"""Shared MetaTrader5 initialize helper (path/env for Wine / multi-install hosts)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional


MT5_PATH_ENV = "MT5_TERMINAL_PATH"


@dataclass(frozen=True)
class MT5InitResult:
    ok: bool
    path_used: Optional[str]
    last_error: Optional[tuple[Any, ...]]
    detail: str


def resolve_mt5_terminal_path(
    *,
    path: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
) -> Optional[str]:
    """Prefer explicit path, then MT5_TERMINAL_PATH env."""
    if path and str(path).strip():
        return str(path).strip()
    environ = env if env is not None else os.environ
    env_path = environ.get(MT5_PATH_ENV)
    if env_path and str(env_path).strip():
        return str(env_path).strip()
    return None


def initialize_mt5(
    mt5_module: Any,
    *,
    path: Optional[str] = None,
    timeout: Optional[int] = None,
    login: Optional[int] = None,
    password: Optional[str] = None,
    server: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
) -> MT5InitResult:
    """
    Initialize MT5 IPC with optional terminal path (required on some Wine hosts).

    Does not invent success: returns last_error when initialize fails.
    Login kwargs are forwarded only when provided (Demo attach).
    """
    resolved = resolve_mt5_terminal_path(path=path, env=env)
    kwargs: dict[str, Any] = {}
    if resolved:
        kwargs["path"] = resolved
    if timeout is not None:
        kwargs["timeout"] = int(timeout)
    if login is not None:
        kwargs["login"] = int(login)
    if password is not None:
        kwargs["password"] = password
    if server is not None:
        kwargs["server"] = server

    ok = bool(mt5_module.initialize(**kwargs) if kwargs else mt5_module.initialize())
    err = None
    try:
        raw = mt5_module.last_error()
    except Exception:
        raw = None
    if isinstance(raw, tuple):
        err = raw
    elif isinstance(raw, list):
        err = tuple(raw)
    elif raw is None:
        err = None
    else:
        # Avoid iterating unittest.mock.Mock / opaque objects.
        err = (raw,)

    if ok:
        return MT5InitResult(ok=True, path_used=resolved, last_error=err, detail="initialized")

    code = err[0] if err else None
    if code == -10003:
        detail = "ipc_terminal_not_found"
    elif code == -6:
        detail = "terminal_authorization_failed"
    else:
        detail = "initialize_failed"
    return MT5InitResult(ok=False, path_used=resolved, last_error=err, detail=detail)
