"""H1 bias helpers for webhook Gate C path (scenario 8)."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple


def parse_h1_bias_fields(payload: Optional[Mapping[str, Any]]) -> Tuple[Optional[str], bool]:
    """
    Extract (h1_bias, bias_known) from webhook/clock JSON.

    Missing keys → bias_known=False (never invent a cancel/reject).
    """
    if not payload:
        return None, False
    if "h1_bias_known" not in payload and "h1_bias" not in payload:
        return None, False

    raw_known = payload.get("h1_bias_known", True if "h1_bias" in payload else False)
    if isinstance(raw_known, bool):
        bias_known = raw_known
    else:
        bias_known = str(raw_known).strip().lower() in {"1", "true", "yes", "on"}

    raw_bias = payload.get("h1_bias")
    if raw_bias is None or str(raw_bias).strip() == "" or str(raw_bias).strip().upper() == "FLAT":
        return None, bias_known
    return str(raw_bias).strip().upper(), bias_known


def coalesce_h1_bias(
    payload: Optional[Mapping[str, Any]],
    live_bias: Optional[str],
    live_known: bool,
) -> Tuple[Optional[str], bool]:
    """Prefer explicit payload bias; else live broker resolve when known."""
    h1_bias, h1_bias_known = parse_h1_bias_fields(payload)
    if h1_bias_known:
        return h1_bias, True
    if live_known:
        return live_bias, True
    return None, False
