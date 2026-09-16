"""Infrastructure verdicts separate from strategy PnL (foundation scenario 24)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

InfraVerdict = Literal["PASS_INFRA", "FAIL_INFRA", "INCONCLUSIVE_INFRA"]


@dataclass(frozen=True)
class InfraReport:
    verdict: InfraVerdict
    identity_ok: bool
    mt5_available: bool
    soak_completed: bool
    detail: str


def classify_infra_evidence(
    *,
    mt5_available: bool,
    identity_ok: bool,
    soak_completed: bool = False,
    soak_pass: Optional[bool] = None,
) -> InfraReport:
    """
    Mac-off / Oracle / Demo runtime evidence must not be scored as strategy edge.

    - Missing MT5 binding → INCONCLUSIVE_INFRA (environment), not strategy FAIL
    - Identity fail with MT5 present → FAIL_INFRA
    - Soak incomplete → INCONCLUSIVE_INFRA
    - Soak completed true/false → PASS_INFRA / FAIL_INFRA
    """
    if not mt5_available:
        return InfraReport(
            "INCONCLUSIVE_INFRA",
            identity_ok=False,
            mt5_available=False,
            soak_completed=False,
            detail="mt5_unavailable_on_host",
        )
    if not identity_ok:
        return InfraReport(
            "FAIL_INFRA",
            identity_ok=False,
            mt5_available=True,
            soak_completed=False,
            detail="broker_identity_gate_failed",
        )
    if not soak_completed or soak_pass is None:
        return InfraReport(
            "INCONCLUSIVE_INFRA",
            identity_ok=True,
            mt5_available=True,
            soak_completed=False,
            detail="soak_not_executed",
        )
    if soak_pass:
        return InfraReport(
            "PASS_INFRA",
            identity_ok=True,
            mt5_available=True,
            soak_completed=True,
            detail="soak_pass",
        )
    return InfraReport(
        "FAIL_INFRA",
        identity_ok=True,
        mt5_available=True,
        soak_completed=True,
        detail="soak_fail",
    )
