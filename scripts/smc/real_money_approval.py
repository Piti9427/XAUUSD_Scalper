"""Separate approval boundary for real-money deployment (foundation story 49).

Demo readiness, SOFTWARE_VERIFIED, and dry_run=False on a Demo account do NOT
authorize live capital. Real-money requires explicit dual approval.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional


REAL_MONEY_ENV = "XAUUSD_REAL_MONEY_APPROVED"


@dataclass(frozen=True)
class RealMoneyApprovalReport:
    ok: bool
    required: bool
    reasons: tuple[str, ...]


def _truthy(value: object) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def evaluate_real_money_approval(
    *,
    dry_run: bool,
    allow_demo_only: bool = True,
    config_approved: bool = False,
    env: Optional[Mapping[str, str]] = None,
) -> RealMoneyApprovalReport:
    """
    Fail closed when live non-demo path is requested without dual approval.

    - dry_run=True → not required
    - dry_run=False + allow_demo_only=True → Demo broker path; not real-money
    - dry_run=False + allow_demo_only=False → requires env + config approved
    """
    if dry_run or allow_demo_only:
        return RealMoneyApprovalReport(ok=True, required=False, reasons=())

    reasons: list[str] = []
    environ = env if env is not None else os.environ
    if not _truthy(environ.get(REAL_MONEY_ENV)):
        reasons.append("missing_env_approval")
    if not _truthy(config_approved):
        reasons.append("missing_config_approval")

    return RealMoneyApprovalReport(
        ok=len(reasons) == 0,
        required=True,
        reasons=tuple(reasons),
    )


def require_real_money_approval(
    *,
    dry_run: bool,
    allow_demo_only: bool = True,
    config_approved: bool = False,
    env: Optional[Mapping[str, str]] = None,
) -> RealMoneyApprovalReport:
    """Evaluate and raise SystemExit when real-money boundary fails closed."""
    report = evaluate_real_money_approval(
        dry_run=dry_run,
        allow_demo_only=allow_demo_only,
        config_approved=config_approved,
        env=env,
    )
    if not report.ok:
        raise SystemExit(
            "real-money approval boundary blocked start: "
            + ",".join(report.reasons)
            + f" (set {REAL_MONEY_ENV}=1 and real_money.approved=true)"
        )
    return report
