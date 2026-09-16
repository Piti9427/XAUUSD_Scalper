"""Stable setup identity and terminal registry (B16 / foundation § scenario 8)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, Optional, Set


def make_setup_id(
    *,
    direction: str,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    sweep_wick: float,
    available_at: str,
    rule_version: str = "s1-s4-mechanical-v1",
) -> str:
    """
    Build a deterministic SETUP_ID from event fields.

    available_at must be a timezone-aware UTC ISO string (or other stable clock key).
    """
    canonical = "|".join(
        [
            rule_version,
            direction.upper(),
            f"{float(entry_price):.5f}",
            f"{float(sl_price):.5f}",
            f"{float(tp_price):.5f}",
            f"{float(sweep_wick):.5f}",
            str(available_at),
        ]
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"SMC_{digest}"


@dataclass
class SetupRegistry:
    """Remember terminal setups so expiry/invalidation cannot revive the same ID."""

    _terminal: Set[str] = field(default_factory=set)
    _reasons: Dict[str, str] = field(default_factory=dict)

    def is_blocked(self, setup_id: Optional[str]) -> bool:
        if not setup_id:
            return False
        return setup_id in self._terminal

    def mark_terminal(self, setup_id: Optional[str], reason: str) -> None:
        if not setup_id:
            return
        self._terminal.add(setup_id)
        self._reasons[setup_id] = reason

    def terminal_reason(self, setup_id: str) -> Optional[str]:
        return self._reasons.get(setup_id)

    def admit(self, setup_id: Optional[str]) -> tuple[bool, str]:
        if not setup_id:
            return True, "ok_missing_id"
        if self.is_blocked(setup_id):
            return False, f"setup_id_terminal:{self._reasons.get(setup_id, 'unknown')}"
        return True, "ok"
