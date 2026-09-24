"""Shared MT5 adapter value types and ownership helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    order_id: Optional[int]
    message: str
    status: str = "OK"  # OK | REJECTED | UNKNOWN


BOT_COMMENT_PREFIX = "SMC_"


def is_bot_owned_comment(comment: Optional[str], order_id: Optional[str] = None) -> bool:
    """True only for comments owned by this strategy — never symbol-only matches."""
    if not comment or not comment.startswith(BOT_COMMENT_PREFIX):
        return False
    if order_id is None:
        return True
    return comment in {f"SMC_{order_id}", f"SMC_Partial_{order_id}"}
