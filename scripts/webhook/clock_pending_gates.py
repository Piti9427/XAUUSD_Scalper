"""Clock pending-cancel phases: news, H1 bias, SL-before-fill + missing quote."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from scripts.smc.quotes import (
    disclose_missing_quote_for_pending_sl,
    pending_sl_touched_before_fill,
)
from scripts.smc.setup_identity import pending_h1_bias_allows
from scripts.webhook.h1_bias import resolve_h1_bias_lazy
from scripts.webhook.pending_cancel import cancel_unfilled_pending
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


async def cancel_pendings_for_news(
    rt: WebhookRuntime,
    *,
    pending_ids: Sequence[str],
    now_utc: datetime,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Scenario 18: cancel unfilled pendings when news gate blocks new risk."""
    cancel_results: List[Dict[str, Any]] = []
    ids = list(pending_ids)
    if rt.news_manager is None or not hasattr(rt.news_manager, "should_cancel_pending"):
        return ids, cancel_results

    events = getattr(rt.news_manager, "events", None)
    schedule_known = bool(
        getattr(rt.news_manager, "schedule_known", events is not None)
    )
    cancel_pending, cancel_reason = await asyncio.to_thread(
        rt.news_manager.should_cancel_pending,
        now_utc,
        events,
        schedule_known=schedule_known,
        window_mins=30,
    )
    if not cancel_pending:
        return ids, cancel_results

    still_pending: List[str] = []
    for oid in ids:
        kept, row = await cancel_unfilled_pending(
            rt,
            order_id=oid,
            intent_reason=f"news_pending_cancel:{cancel_reason}",
            lifecycle_reason=f"news_pending_cancel:{cancel_reason}",
            terminal_reason=f"news_pending_cancel:{cancel_reason}",
            result_reason=cancel_reason,
        )
        if kept:
            still_pending.append(oid)
        cancel_results.append(row)
    return still_pending, cancel_results


async def cancel_pendings_for_h1_bias(
    rt: WebhookRuntime,
    *,
    pending_ids: Sequence[str],
    clock_payload: Dict[str, Any],
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Scenario 8: known H1 bias flip cancels opposing unfilled pendings."""
    h1_bias_cancels: List[Dict[str, Any]] = []
    ids = list(pending_ids)
    h1_bias, h1_bias_known = await asyncio.to_thread(
        resolve_h1_bias_lazy,
        clock_payload,
        rt.adapter.resolve_live_h1_bias,
    )
    if not h1_bias_known:
        return ids, h1_bias_cancels

    still_pending: List[str] = []
    for oid in ids:
        pending_dir = await asyncio.to_thread(rt.adapter.get_pending_direction, oid)
        if not pending_dir:
            still_pending.append(oid)
            continue
        bias_ok, bias_reason = pending_h1_bias_allows(
            pending_direction=pending_dir,
            h1_bias=h1_bias,
            bias_known=True,
        )
        if bias_ok:
            still_pending.append(oid)
            continue
        intent_reason = f"H1 bias invalidation: {bias_reason}"
        kept, row = await cancel_unfilled_pending(
            rt,
            order_id=oid,
            intent_reason=intent_reason,
            lifecycle_reason=f"h1_bias_invalidated:{bias_reason}",
            terminal_reason=bias_reason,
            result_reason=bias_reason,
        )
        if kept:
            still_pending.append(oid)
        h1_bias_cancels.append(row)
    return still_pending, h1_bias_cancels


async def cancel_pendings_sl_before_fill(
    rt: WebhookRuntime,
    *,
    pending_ids: Sequence[str],
    clock_payload: Dict[str, Any],
) -> Tuple[List[str], List[Dict[str, Any]], List[Dict[str, Any]], Optional[float], Optional[float]]:
    """
    B15 / S1–S4: SL before fill using clock OHLC or live bid/ask.

    Missing both → disclose; never invent synthetic high/low.
    Returns (pending_ids, sl_cancels, missing_quote_rows, bar_high, bar_low).
    """
    sl_before_fill_cancels: List[Dict[str, Any]] = []
    missing_quote_disclosures: List[Dict[str, Any]] = []
    ids = list(pending_ids)

    bar_high = None
    bar_low = None
    have_ohlc = isinstance(clock_payload.get("high"), (int, float)) and isinstance(
        clock_payload.get("low"), (int, float)
    )
    if have_ohlc:
        bar_high = float(clock_payload["high"])
        bar_low = float(clock_payload["low"])
    else:
        quotes = await asyncio.to_thread(rt.adapter.get_market_quotes)
        if quotes and quotes.get("ask") is not None and quotes.get("bid") is not None:
            bar_high = float(quotes["ask"])
            bar_low = float(quotes["bid"])

    if bar_high is None or bar_low is None:
        missing_quote_disclosures = disclose_missing_quote_for_pending_sl(
            pending_order_ids=ids,
            have_ohlc=False,
            have_live_quotes=False,
        )
        for row in missing_quote_disclosures:
            await asyncio.to_thread(
                rt.adapter.log_lifecycle_event,
                event_type="MISSING_QUOTE",
                order_id=row["order_id"],
                reason="missing_quote:sl_before_fill_check",
            )
            logger.info(
                "Clock missing quote disclosure for pending %s (no invent OHLC)",
                row["order_id"],
            )
        return ids, sl_before_fill_cancels, missing_quote_disclosures, bar_high, bar_low

    still_pending: List[str] = []
    for oid in ids:
        geom = await asyncio.to_thread(rt.adapter.get_pending_geometry, oid)
        if not geom or geom.get("sl_price") is None or not geom.get("direction"):
            still_pending.append(oid)
            continue
        limit_price = geom.get("limit_price")
        if limit_price is None:
            limit_price = geom["sl_price"]
        if not pending_sl_touched_before_fill(
            direction=str(geom["direction"]),
            limit_price=float(limit_price),
            sl_price=float(geom["sl_price"]),
            bar_high=bar_high,
            bar_low=bar_low,
        ):
            still_pending.append(oid)
            continue
        kept, row = await cancel_unfilled_pending(
            rt,
            order_id=oid,
            intent_reason="SL before fill: planned stop reached while pending",
            lifecycle_reason="sl_before_fill",
            terminal_reason="sl_before_fill",
            result_reason="sl_before_fill",
        )
        if kept:
            still_pending.append(oid)
        sl_before_fill_cancels.append(row)
    return (
        still_pending,
        sl_before_fill_cancels,
        missing_quote_disclosures,
        bar_high,
        bar_low,
    )
