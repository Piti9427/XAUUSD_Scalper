"""Replay report kinds for foundation stories 39–40.

Separates theoretical setup tape from USD 500 executable replay and refuses
shared-account parity claims when external account events are absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

from scripts.smc.affordability import AffordabilityReport, build_affordability_report


class ReplayKind(str, Enum):
    THEORETICAL_TAPE = "theoretical_tape"
    EXECUTABLE_USD500 = "executable_usd500"
    SHARED_ACCOUNT = "shared_account"
    DEMO_ACTUAL = "demo_actual"


EXECUTABLE_DEMO_BALANCE = 500.0


@dataclass(frozen=True)
class ReplayReport:
    kind: ReplayKind
    initial_balance: float
    trade_count: int
    net_profit: float
    win_rate: float
    shared_account_parity_claimed: bool
    shared_account_parity_ok: bool
    affordability: Optional[AffordabilityReport]
    notes: tuple[str, ...]


def build_replay_report(
    *,
    kind: ReplayKind,
    initial_balance: float,
    trade_count: int,
    net_profit: float,
    win_rate: float,
    external_account_events: Optional[Sequence[Mapping[str, Any]]] = None,
    risk_pct: float = 0.005,
) -> ReplayReport:
    """
    Label a replay/Demo summary so research tape cannot be mistaken for USD 500
    executable results, and shared-account parity cannot be claimed without events.
    """
    notes: list[str] = []
    affordability: Optional[AffordabilityReport] = None
    parity_claimed = kind == ReplayKind.SHARED_ACCOUNT
    events = list(external_account_events or ())

    if kind == ReplayKind.EXECUTABLE_USD500:
        if abs(float(initial_balance) - EXECUTABLE_DEMO_BALANCE) > 1e-9:
            notes.append("executable_balance_mismatch")
        affordability = build_affordability_report(
            balance=EXECUTABLE_DEMO_BALANCE,
            risk_pct=risk_pct,
        )
        notes.append("usd500_executable_not_theoretical_tape")

    if kind == ReplayKind.THEORETICAL_TAPE:
        notes.append("theoretical_tape_not_account_performance")

    if kind == ReplayKind.SHARED_ACCOUNT:
        if not events:
            notes.append("missing_external_account_events_no_parity")
            parity_ok = False
        else:
            notes.append("shared_account_events_present")
            parity_ok = True
    else:
        # Non-shared kinds must not advertise shared-account live parity.
        parity_ok = False
        if parity_claimed:
            notes.append("parity_claim_invalid_for_kind")

    if kind == ReplayKind.DEMO_ACTUAL:
        notes.append("demo_actual_requires_broker_evidence")

    return ReplayReport(
        kind=kind,
        initial_balance=float(initial_balance),
        trade_count=int(trade_count),
        net_profit=float(net_profit),
        win_rate=float(win_rate),
        shared_account_parity_claimed=parity_claimed,
        shared_account_parity_ok=parity_ok,
        affordability=affordability,
        notes=tuple(notes),
    )


def assert_not_conflated(
    *,
    theoretical: ReplayReport,
    executable: ReplayReport,
) -> None:
    """Fail closed if theoretical and executable reports share the same kind label."""
    if theoretical.kind == executable.kind:
        raise ValueError("theoretical and executable reports must use distinct kinds")
    if theoretical.kind != ReplayKind.THEORETICAL_TAPE:
        raise ValueError("theoretical report must be THEORETICAL_TAPE")
    if executable.kind != ReplayKind.EXECUTABLE_USD500:
        raise ValueError("executable report must be EXECUTABLE_USD500")
