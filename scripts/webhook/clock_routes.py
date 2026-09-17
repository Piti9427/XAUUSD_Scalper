"""Internal clock reconciler route (scenarios 8/18/19 + lifecycle)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import BackgroundTasks, Depends, FastAPI, Request

from scripts.webhook.clock_lifecycle_apply import (
    apply_lifecycle_closes,
    apply_lifecycle_fills,
    apply_lifecycle_ttl_cancels,
)
from scripts.webhook.clock_pending_gates import (
    cancel_pendings_for_h1_bias,
    cancel_pendings_for_news,
    cancel_pendings_sl_before_fill,
)
from scripts.webhook.clock_risk_halt import (
    flatten_on_risk_halt,
    observe_and_persist_risk_halt,
)
from scripts.webhook.clock_time_exits import run_clock_time_exits
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


def register_clock_route(app: FastAPI, rt: WebhookRuntime) -> None:
    @app.post("/internal/clock")
    async def handle_clock_tick(
        request: Request,
        background_tasks: BackgroundTasks,
        authorized: bool = Depends(rt.verify_auth),
    ):
        """
        Periodic reconciler: news-cancel unfilled pendings + wall-clock TIME_EXIT.

        Scenario 18/19 — never force-close filled positions on news; never notify
        TRADE CLOSED without broker evidence.
        Optional JSON body may carry h1_bias / h1_bias_known (scenario 8).
        """
        from scripts.smc.broker_lifecycle import reconcile_broker_lifecycle

        clock_payload: Dict[str, Any] = {}
        try:
            parsed = await request.json()
            if isinstance(parsed, dict):
                clock_payload = parsed
        except Exception:
            clock_payload = {}

        now_utc = datetime.now(timezone.utc)
        uncertain_results = []
        lifecycle = await asyncio.to_thread(
            reconcile_broker_lifecycle,
            rt.adapter,
            now=now_utc,
            order_ttl_bars=rt.order_ttl_bars,
            bar_minutes=rt.bar_minutes,
        )

        # Story 35: reconcile uncertain intents before admitting new risk / more submits.
        uncertain_ids = await asyncio.to_thread(rt.adapter.list_uncertain_order_ids)
        for oid in uncertain_ids:
            outcome = await asyncio.to_thread(rt.adapter.reconcile_uncertain, oid)
            uncertain_results.append({"order_id": oid, "outcome": outcome})
            logger.info("Clock reconcile_uncertain %s -> %s", oid, outcome)

        # Stories 5–7: disclose bot vs manual vs cash_flow deal cash separately.
        account_pnl_rows = await asyncio.to_thread(rt.adapter.sync_classified_account_pnl)

        await observe_and_persist_risk_halt(
            rt,
            now_utc=now_utc,
            broker_closes=lifecycle.get("broker_closes", []),
        )

        await apply_lifecycle_fills(
            rt,
            fill_rows=lifecycle.get("broker_fills", []),
            now_utc=now_utc,
            background_tasks=background_tasks,
        )
        await apply_lifecycle_ttl_cancels(
            rt, ttl_rows=lifecycle.get("ttl_cancels", [])
        )
        await apply_lifecycle_closes(
            rt,
            close_rows=lifecycle.get("broker_closes", []),
            background_tasks=background_tasks,
        )

        # Scenario 18 / 8 / B15 / story 10: news, H1, SL-before-fill, risk-halt
        pending_ids = await asyncio.to_thread(rt.adapter.list_unfilled_pendings)
        pending_ids, risk_halt_cancels, risk_halt_closes = await flatten_on_risk_halt(
            rt, pending_ids=pending_ids
        )
        pending_ids, cancel_results = await cancel_pendings_for_news(
            rt, pending_ids=pending_ids, now_utc=now_utc
        )
        pending_ids, h1_bias_cancels = await cancel_pendings_for_h1_bias(
            rt, pending_ids=pending_ids, clock_payload=clock_payload
        )
        (
            pending_ids,
            sl_before_fill_cancels,
            missing_quote_disclosures,
            bar_high,
            bar_low,
        ) = await cancel_pendings_sl_before_fill(
            rt, pending_ids=pending_ids, clock_payload=clock_payload
        )

        fills, plans, exit_results, exit_missing = await run_clock_time_exits(
            rt,
            now_utc=now_utc,
            bar_high=bar_high,
            bar_low=bar_low,
            background_tasks=background_tasks,
        )
        missing_quote_disclosures.extend(exit_missing)

        has_work = bool(
            cancel_results
            or risk_halt_cancels
            or risk_halt_closes
            or h1_bias_cancels
            or sl_before_fill_cancels
            or missing_quote_disclosures
            or exit_results
            or uncertain_results
            or account_pnl_rows
            or lifecycle.get("ttl_cancels")
            or lifecycle.get("broker_fills")
            or lifecycle.get("broker_closes")
        )
        status_out = "ok"
        reason_out = None
        if rt.max_hold_bars is None and not plans and not has_work:
            # Idle tick: rollover planner still armed; max_hold optional.
            status_out = "ok"
            reason_out = "idle_clock_tick"
        return {
            "status": status_out,
            "action": "CLOCK_TICK",
            "checked": len(fills),
            "cancels": cancel_results,
            "risk_halt_cancels": risk_halt_cancels,
            "risk_halt_closes": risk_halt_closes,
            "h1_bias_cancels": h1_bias_cancels,
            "sl_before_fill_cancels": sl_before_fill_cancels,
            "missing_quote_disclosures": missing_quote_disclosures,
            "exits": exit_results,
            "uncertain": uncertain_results,
            "account_pnl": account_pnl_rows,
            "lifecycle": lifecycle,
            "reason": reason_out,
            "max_hold_bars": rt.max_hold_bars,
            "timestamp": now_utc.isoformat(),
        }
