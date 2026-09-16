"""Two-tier webhook idempotency helpers (memory + adapter journal)."""

from __future__ import annotations

from typing import Any, Callable, Set, Tuple


def make_idempotency_helpers(
    adapter: Any,
    cache: Set[Tuple[str, str]],
) -> tuple[Callable[[str, str], bool], Callable[..., None]]:
    """Build is_processed / mark_processed closures over adapter + cache."""

    def is_processed(oid: str, ev: str) -> bool:
        if (oid, ev) in cache:
            return True
        if adapter.is_webhook_processed(oid, ev):
            cache.add((oid, ev))
            return True
        return False

    def mark_processed(oid: str, ev: str, status_str: str = "success") -> None:
        cache.add((oid, ev))
        adapter.mark_webhook_processed(oid, ev, status=status_str)

    return is_processed, mark_processed
