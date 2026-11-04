"""Exclusive, read-only Demo broker evidence. Never dispatch an order."""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import time
import math
import MetaTrader5 as mt5

root = Path(r"Z:\home\ubuntu\c22-oracle-compat-evidence\market-open-preparation")
cfg = json.loads(Path(r"Z:\home\ubuntu\c22-private\demo-account.json").read_text())
started = time.monotonic()
try:
    ok = mt5.initialize(
        r"C:\tools\mt5-c22-demo\terminal64.exe",
        login=int(cfg["login"]),
        password=cfg["password"],
        server=cfg["server"],
        timeout=90000,
    )
    assert ok, "initialize_failed"
    account, terminal = mt5.account_info(), mt5.terminal_info()
    assert account and terminal and terminal.connected, "not_connected"
    assert (
        account.login == int(cfg["login"])
        and account.server == cfg["server"]
        and account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
    ), "demo_identity_required"
    fingerprint = hashlib.sha256((account.server + ":" + str(account.login)).encode()).hexdigest()[
        :16
    ]
    assert fingerprint == cfg["expected_fingerprint"], "fingerprint_mismatch"
    positions, orders = mt5.positions_get(), mt5.orders_get()
    assert positions is not None and orders is not None and not positions and not orders, (
        "account_not_verified_flat"
    )
    spec, tick = mt5.symbol_info("XAUUSDm"), mt5.symbol_info_tick("XAUUSDm")
    assert spec and tick, "symbol_or_quote_missing"
    spec_fields = (
        "trade_contract_size",
        "trade_tick_size",
        "trade_tick_value",
        "point",
        "digits",
        "volume_min",
        "volume_max",
        "volume_step",
        "trade_stops_level",
        "trade_freeze_level",
        "trade_mode",
        "filling_mode",
        "swap_mode",
        "swap_long",
        "swap_short",
        "swap_rollover3days",
        "currency_profit",
        "currency_margin",
    )
    fields = {k: getattr(spec, k) for k in spec_fields}
    fields.update(
        {
            k: getattr(spec, k, None)
            for k in (
                "swap_sunday",
                "swap_monday",
                "swap_tuesday",
                "swap_wednesday",
                "swap_thursday",
                "swap_friday",
                "swap_saturday",
            )
        }
    )
    history_start = datetime(1970, 1, 1, tzinfo=timezone.utc)
    history_deadline = time.monotonic() + 60
    # Cold terminals can report [] before history synchronization finishes.
    # Do not turn an empty response into evidence of no past charges/trades.
    while True:
        history_end = datetime.now(timezone.utc)
        deals = mt5.history_deals_get(history_start, history_end)
        count = mt5.history_deals_total(history_start, history_end)
        if (
            deals is not None
            and count == len(deals)
            and len(deals) > 0
            and all(
                math.isfinite(float(getattr(d, k)))
                for d in deals
                for k in ("profit", "commission", "fee", "swap")
            )
            and abs(
                sum(
                    float(getattr(d, k))
                    for d in deals
                    for k in ("profit", "commission", "fee", "swap")
                )
                - account.balance
            )
            <= 0.02
        ):
            break
        if time.monotonic() >= history_deadline:
            raise ValueError("history_not_reconciled_to_balance")
        time.sleep(1)
    keys = (
        "ticket",
        "position_id",
        "magic",
        "type",
        "entry",
        "volume",
        "time_msc",
        "price",
        "profit",
        "commission",
        "fee",
        "swap",
        "symbol",
    )
    ledger = [{k: getattr(d, k) for k in keys} for d in deals]
    calculations = []
    for side in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL):
        sign = 1 if side == mt5.ORDER_TYPE_BUY else -1
        entry = float(tick.ask if sign == 1 else tick.bid)
        sl, tp = round(entry - sign * 10, spec.digits), round(entry + sign * 20, spec.digits)
        request = dict(
            action=mt5.TRADE_ACTION_DEAL,
            symbol="XAUUSDm",
            volume=0.01,
            type=side,
            price=entry,
            sl=sl,
            tp=tp,
            deviation=100,
            magic=0,
            comment="C22_READONLY_CHECK",
            type_time=mt5.ORDER_TIME_GTC,
            type_filling=mt5.ORDER_FILLING_FOK,
        )
        margin = mt5.order_calc_margin(side, "XAUUSDm", 0.01, entry)
        pnl = mt5.order_calc_profit(side, "XAUUSDm", 0.01, entry, sl)
        check = mt5.order_check(request)
        calculations.append(
            dict(
                side="BUY" if sign == 1 else "SELL",
                volume=0.01,
                margin=margin,
                finite_margin=margin is not None and math.isfinite(margin) and margin >= 0,
                diagnostic_stop_loss=pnl,
                order_check=None
                if check is None
                else {
                    k: getattr(check, k)
                    for k in ("retcode", "comment", "balance", "equity", "margin", "margin_free")
                },
                scope="Synthetic API geometry only; not C22 signal/admission or sending authorization",
            )
        )
    evidence = dict(
        captured_utc=datetime.now(timezone.utc).isoformat(),
        account_fingerprint=fingerprint,
        demo_verified=True,
        hedging_verified=account.margin_mode == mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
        account={
            k: getattr(account, k)
            for k in (
                "currency",
                "balance",
                "equity",
                "margin_free",
                "leverage",
                "trade_allowed",
                "trade_expert",
            )
        },
        terminal=dict(
            connected=terminal.connected,
            trade_allowed=terminal.trade_allowed,
            tradeapi_disabled=terminal.tradeapi_disabled,
        ),
        positions=0,
        orders=0,
        symbol="XAUUSDm",
        spec=fields,
        tick=dict(
            time_msc=tick.time_msc,
            bid=tick.bid,
            ask=tick.ask,
            age_seconds=time.time() - tick.time_msc / 1000,
        ),
        diagnostics=calculations,
        history_start_utc=history_start.isoformat(),
        history_deals=ledger,
        order_send_called=False,
        elapsed_seconds=time.monotonic() - started,
    )
    root.mkdir(parents=True, exist_ok=True)
    (root / "broker-evidence.json").write_text(
        json.dumps(evidence, indent=2, allow_nan=False) + "\n"
    )
    print(
        "C22_READONLY_BROKER",
        json.dumps({k: v for k, v in evidence.items() if k != "history_deals"}),
        flush=True,
    )
    print("C22_DEAL_COUNTS", len(ledger), flush=True)
finally:
    mt5.shutdown()
