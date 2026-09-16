"""Account margin mode gate for Demo ownership isolation (Issue #1 scenario 12)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# MetaTrader5 ACCOUNT_MARGIN_MODE_* (common values)
MARGIN_MODE_RETAIL_NETTING = 0
MARGIN_MODE_EXCHANGE_NETTING = 1
MARGIN_MODE_RETAIL_HEDGING = 2

NETTING_MODES = frozenset({MARGIN_MODE_RETAIL_NETTING, MARGIN_MODE_EXCHANGE_NETTING, "netting", "NETTING"})
HEDGING_MODES = frozenset({MARGIN_MODE_RETAIL_HEDGING, "hedging", "HEDGING", "account_margin_mode_retail_hedging"})


@dataclass(frozen=True)
class AccountModeReport:
    ok: bool
    margin_mode: Optional[str]
    reasons: tuple[str, ...]


def verify_account_mode(
    *,
    account_info: Optional[Any] = None,
    require_hedging: bool = True,
) -> AccountModeReport:
    """
    Fail closed when ownership cannot be isolated safely.

    Comment-scoped bot ownership (SMC_*) requires hedging (or equivalent).
    Netting accounts share one net position per symbol — Demo execution gate fails.
    """
    reasons: list[str] = []
    raw = getattr(account_info, "margin_mode", None) if account_info is not None else None
    if account_info is None:
        reasons.append("missing_account_info")
    if raw is None:
        reasons.append("margin_mode_unknown")
    elif require_hedging and raw in NETTING_MODES:
        reasons.append("netting_mode_blocks_ownership")
    elif require_hedging and raw not in HEDGING_MODES:
        reasons.append("margin_mode_unsupported")

    return AccountModeReport(
        ok=len(reasons) == 0,
        margin_mode=str(raw) if raw is not None else None,
        reasons=tuple(reasons),
    )
