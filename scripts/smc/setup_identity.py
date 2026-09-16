"""Stable setup identity and terminal registry (B16 / foundation § scenario 8)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Set, Union


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
    _persist_path: Optional[Path] = field(default=None, repr=False)

    def is_blocked(self, setup_id: Optional[str]) -> bool:
        if not setup_id:
            return False
        return setup_id in self._terminal

    def mark_terminal(self, setup_id: Optional[str], reason: str) -> None:
        if not setup_id:
            return
        self._terminal.add(setup_id)
        self._reasons[setup_id] = reason
        self._persist()

    def terminal_reason(self, setup_id: str) -> Optional[str]:
        return self._reasons.get(setup_id)

    def admit(self, setup_id: Optional[str]) -> tuple[bool, str]:
        if not setup_id:
            return True, "ok_missing_id"
        if self.is_blocked(setup_id):
            return False, f"setup_id_terminal:{self._reasons.get(setup_id, 'unknown')}"
        return True, "ok"

    def to_dict(self) -> Dict[str, str]:
        """Serialize terminal reasons (id → reason)."""
        return dict(self._reasons)

    def _persist(self) -> None:
        if self._persist_path is None:
            return
        save_setup_registry(self._persist_path, self)


def load_setup_registry(path: Union[str, Path]) -> SetupRegistry:
    """
    Load terminal setup IDs from disk.

    Missing/corrupt files start empty (fail closed on admit still works once
    marks exist). Restart after expiry must not revive the same SETUP_ID.
    """
    path = Path(path)
    registry = SetupRegistry(_persist_path=path)
    if not path.is_file():
        return registry
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return registry
    reasons = payload.get("reasons") if isinstance(payload, dict) else None
    if not isinstance(reasons, dict):
        return registry
    for setup_id, reason in reasons.items():
        if not setup_id:
            continue
        registry._terminal.add(str(setup_id))
        registry._reasons[str(setup_id)] = str(reason or "unknown")
    return registry


def save_setup_registry(path: Union[str, Path], registry: SetupRegistry) -> None:
    """Atomically persist terminal setup identities for restart survival."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "reasons": registry.to_dict(),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def pending_h1_bias_allows(
    *,
    pending_direction: str,
    h1_bias: Optional[str],
    bias_known: bool,
) -> tuple[bool, str]:
    """
    Pending must die when known H1 bias no longer supports its direction.

    Unknown bias (caller could not compute) does not invent a cancel.
    Flat bias (bias_known and h1_bias is None) invalidates pending.
    pending_direction / h1_bias are Direction.value strings or Direction enums.
    """
    if not bias_known:
        return True, "ok_bias_unknown"
    if h1_bias is None:
        return False, "h1_bias_flat"
    pending = getattr(pending_direction, "value", pending_direction)
    bias = getattr(h1_bias, "value", h1_bias)
    if str(bias).upper() != str(pending).upper():
        return False, "h1_bias_invalidated"
    return True, "ok"
