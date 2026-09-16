"""Dataset provenance reason codes for foundation Gate B (B20)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProvenanceReport:
    ok: bool
    code: str
    detail: str = ""


def classify_dataset_provenance(
    *,
    has_m5: bool,
    has_h1: bool,
    has_ticks: bool,
    timezone_aware_utc: bool,
    source_label: Optional[str] = None,
    is_proxy: bool = False,
) -> ProvenanceReport:
    """
    Return a distinct reason code for missing/proxy/bad-time data.

    These codes must not collapse into ordinary no-setup.
    """
    if not has_m5:
        return ProvenanceReport(False, "DATA_INSUFFICIENT_M5", "M5 bars missing")
    if not has_h1:
        return ProvenanceReport(False, "DATA_INSUFFICIENT_H1", "H1 bars missing")
    if not timezone_aware_utc:
        return ProvenanceReport(False, "DATA_BAD_TIMEZONE", "timestamps not timezone-aware UTC")
    if is_proxy:
        return ProvenanceReport(
            False,
            "DATA_PROXY_FEED",
            f"proxy feed not accepted for PASS claims ({source_label or 'unknown'})",
        )
    if not has_ticks:
        return ProvenanceReport(
            True,
            "DATA_OHLC_ONLY",
            "ticks absent; dual-touch exits must stay AMBIGUOUS",
        )
    return ProvenanceReport(True, "DATA_OK", source_label or "ok")
