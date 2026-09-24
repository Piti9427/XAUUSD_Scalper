"""Pure broker lifecycle reconciliation helpers for foundation BaselinePlay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PendingExposure:
    order_id: str
    requested_volume: float
    filled_volume: float = 0.0
    cancel_requested: bool = False
    broker_pending_volume: Optional[float] = None
    broker_position_volume: Optional[float] = None


@dataclass(frozen=True)
class ReconcileDecision:
    status: str
    filled_volume: float
    residual_pending_volume: float
    reason: str


def reconcile_pending_exposure(state: PendingExposure) -> ReconcileDecision:
    """
    Reconcile fill / cancel races without inventing broker state.

    Rules:
    - If broker reports a position/fill while cancel was requested, keep the fill.
    - Residual pending volume stays visible until broker confirms cancel/expiry.
    - Missing broker evidence remains uncertain (do not auto-reject).
    """
    filled = max(float(state.filled_volume), float(state.broker_position_volume or 0.0))
    if state.broker_pending_volume is not None:
        residual = max(0.0, float(state.broker_pending_volume))
    else:
        residual = max(0.0, float(state.requested_volume) - filled)

    if filled > 0 and state.cancel_requested:
        return ReconcileDecision(
            status="filled_during_cancel",
            filled_volume=filled,
            residual_pending_volume=residual,
            reason="broker filled before cancel acknowledgement",
        )
    if filled > 0 and residual > 0:
        return ReconcileDecision(
            status="partial_fill_with_residual",
            filled_volume=filled,
            residual_pending_volume=residual,
            reason="filled volume and residual pending coexist",
        )
    if filled > 0 and residual == 0:
        return ReconcileDecision(
            status="filled",
            filled_volume=filled,
            residual_pending_volume=0.0,
            reason="fully filled",
        )
    if state.cancel_requested and residual == 0 and state.broker_pending_volume == 0.0:
        return ReconcileDecision(
            status="canceled",
            filled_volume=0.0,
            residual_pending_volume=0.0,
            reason="broker confirmed cancel with flat exposure",
        )
    if state.broker_pending_volume is None and state.broker_position_volume is None:
        return ReconcileDecision(
            status="uncertain",
            filled_volume=filled,
            residual_pending_volume=residual,
            reason="missing broker evidence; do not retry blindly",
        )
    return ReconcileDecision(
        status="pending",
        filled_volume=filled,
        residual_pending_volume=residual,
        reason="awaiting broker fill or cancel",
    )
