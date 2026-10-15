#!/usr/bin/env python3
"""
Dry-Run Verification Script for XAUUSD Webhook Bridge.
Runs end-to-end verification of the FastAPI ASGI app without external network dependencies.
"""

import sys
import os
import tempfile
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.webhook_bridge import create_app


def _fresh_time(offset_minutes: int = 0) -> str:
    """Wall-clock UTC string so story-32 admission does not treat fixtures as stale."""
    return (datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def run_verification():
    print("=" * 60)
    print("Starting End-to-End Dry-Run Verification...")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "verify_trades.db")
        secret = "VERIFY_SECRET_999"
        app = create_app(
            auth_token=secret,
            dry_run=True,
            db_path=db_path,
            account_balance=200.0,
            risk_pct=0.01,
            max_daily_losses=2,
            rollover_hour_utc=20,
            rollover_minute_utc=55,
        )
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {secret}"}

        # 1. Health check
        print("[1/8] Verifying Health Check Endpoint (/health)...")
        res = client.get("/health")
        assert res.status_code == 200, f"Health check failed: {res.text}"
        data = res.json()
        assert data["status"] == "ok"
        assert data["mode"] == "dry-run"
        assert data["daily_realized_losses"] == 0
        assert data["circuit_breaker_tripped"] is False
        print("  -> Health Check OK: mode=dry-run, equity=200.0, losses=0")

        # 2. SETUP_PENDING Limit Placement
        print("[2/8] Verifying SETUP_PENDING (BUY Limit Placement)...")
        payload_setup = {
            "event": "SETUP_PENDING",
            "order_id": "VERIFY_XAU_01",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 2650.00,
            "sl": 2645.00,
            "tp1": 2655.00,
            "tp2": 2662.50,
            "ttl": 4,
            "time": _fresh_time(2),
        }
        res = client.post("/webhook/tradingview", json=payload_setup, headers=headers)
        assert res.status_code == 200, f"SETUP_PENDING failed: {res.text}"
        data = res.json()
        assert data["status"] == "success", data
        assert data["action"] == "LIMIT_PLACED"
        assert data["lot_size"] == 0.20, f"Expected 0.20 lots, got {data['lot_size']}"
        assert data["ticket"] is not None
        print(f"  -> SETUP_PENDING OK: lot_size={data['lot_size']}, ticket={data['ticket']}")

        # 3. Two-Tier In-Memory Idempotency Fast Path
        print("[3/8] Verifying Two-Tier Idempotency Rejection (Duplicate Event)...")
        res_dup = client.post("/webhook/tradingview", json=payload_setup, headers=headers)
        assert res_dup.status_code == 200
        data_dup = res_dup.json()
        assert data_dup["status"] == "ignored_duplicate"
        print("  -> Idempotency OK: duplicate rejected instantly via in-memory cache")

        # 4. ORDER_FILLED
        print("[4/8] Verifying ORDER_FILLED Event...")
        payload_fill = {
            "event": "ORDER_FILLED",
            "order_id": "VERIFY_XAU_01",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "entry": 2650.00,
            "sl": 2645.00,
            "tp1": 2655.00,
            "tp2": 2662.50,
            "time": _fresh_time(1),
        }
        res = client.post("/webhook/tradingview", json=payload_fill, headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        print("  -> ORDER_FILLED OK: active trade synchronized")

        # 5. TP1_HIT_MOVE_BE blocked under foundation BaselinePlay defaults
        print("[5/8] Verifying TP1_HIT_MOVE_BE rejected when partial/BE disabled...")
        payload_tp1 = {
            "event": "TP1_HIT_MOVE_BE",
            "order_id": "VERIFY_XAU_01",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "action": "PARTIAL_CLOSE",
            "close_percent": 50,
            "entry": 2650.00,
            "new_sl": 2650.10,
            "time": _fresh_time(0),
        }
        res = client.post("/webhook/tradingview", json=payload_tp1, headers=headers)
        assert res.status_code == 200
        data_tp1 = res.json()
        assert data_tp1["status"] == "rejected", data_tp1
        assert "partial_tp_enabled=False" in data_tp1["reason"]
        print("  -> TP1_HIT_MOVE_BE correctly blocked under foundation defaults")

        # 6. TRADE_CLOSED (Runner TP2 Hit)
        print("[6/8] Verifying TRADE_CLOSED Event (TP2 Runner Hit)...")
        payload_closed = {
            "event": "TRADE_CLOSED",
            "order_id": "VERIFY_XAU_01",
            "symbol": "XAUUSD",
            "reason": "FULL TP2 HIT (+2.5R)",
            "pnl_r": 2.5,
            "pnl_dollar": 250.0,
            "time": _fresh_time(0),
        }
        res = client.post("/webhook/tradingview", json=payload_closed, headers=headers)
        assert res.status_code == 200
        data_closed = res.json()
        assert data_closed["status"] == "success"
        assert data_closed["pnl_r"] == 2.5
        assert data_closed["pnl_dollar"] == 250.0
        print(f"  -> TRADE_CLOSED OK: PnL logged (+2.5R / ${data_closed['pnl_dollar']:.2f})")

        # 7. ORDER_CANCELED (TTL Expired)
        print("[7/8] Verifying ORDER_CANCELED Event (Pending TTL Expired)...")
        payload_setup2 = {
            "event": "SETUP_PENDING",
            "order_id": "VERIFY_XAU_02",
            "symbol": "XAUUSD",
            "dir": "SELL",
            "limit": 2670.00,
            "sl": 2675.00,
            "time": _fresh_time(0),
        }
        setup2 = client.post("/webhook/tradingview", json=payload_setup2, headers=headers)
        assert setup2.status_code == 200
        assert setup2.json()["status"] == "success", setup2.json()
        payload_cancel = {
            "event": "ORDER_CANCELED",
            "order_id": "VERIFY_XAU_02",
            "symbol": "XAUUSD",
            "reason": "TTL_EXPIRED (4 bars elapsed)",
            "time": _fresh_time(0),
        }
        res = client.post("/webhook/tradingview", json=payload_cancel, headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        assert res.json()["action"] == "ORDER_CANCELED"
        print("  -> ORDER_CANCELED OK: pending limit canceled with targeted scoping")

        # 8. Daily Circuit Breaker Guard (ADR-011)
        print("[8/8] Verifying Daily Circuit Breaker Guard (ADR-011)...")
        adapter = app.state.adapter
        # Simulate 2 consecutive losses today in SQLite
        adapter.log_lifecycle_event(
            event_type="TRADE_CLOSED", pnl_dollar=-100.0, pnl_r=-1.0, reason="SL Hit 1"
        )
        adapter.log_lifecycle_event(
            event_type="TRADE_CLOSED", pnl_dollar=-100.0, pnl_r=-1.0, reason="SL Hit 2"
        )
        payload_setup3 = {
            "event": "SETUP_PENDING",
            "order_id": "VERIFY_XAU_03",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "limit": 2650.00,
            "sl": 2645.00,
            "time": _fresh_time(0),
        }
        res = client.post("/webhook/tradingview", json=payload_setup3, headers=headers)
        assert res.status_code == 200
        data_cb = res.json()
        assert data_cb["status"] == "rejected"
        assert "Circuit Breaker" in data_cb["reason"]
        print("  -> Circuit Breaker OK: 3rd trade successfully blocked after 2 daily losses")

        # Cleanup adapter
        if hasattr(app.state, "adapter") and app.state.adapter:
            app.state.adapter.close()

    print("=" * 60)
    print("ALL 8 DRY-RUN VERIFICATION GATES PASSED 100%!")
    print("=" * 60)


if __name__ == "__main__":
    run_verification()
