"""Read-only B1-FINAL preflight snapshot for the configured Standard Demo (Wine Python).

Writes identity as a boolean only. Uses order_calc_profit/order_calc_margin,
which are calculations; order_send/order_check are never called.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

SYMBOL = "XAUUSDm"
ATR_BARS = 6000
SPEC_KEYS = (
    "name",
    "trade_mode",
    "volume_min",
    "volume_step",
    "volume_max",
    "trade_tick_size",
    "trade_tick_value",
    "point",
    "digits",
    "trade_stops_level",
    "trade_freeze_level",
    "filling_mode",
    "trade_exemode",
    "trade_calc_mode",
    "trade_contract_size",
    "swap_long",
    "swap_short",
    "swap_mode",
    "currency_profit",
    "currency_margin",
)


def wilder_atr(rates):
    """Arithmetic 14-bar seed then Wilder recursion, first TR = high-low (B1 convention)."""
    out, total, atr = [], 0.0, None
    for i, bar in enumerate(rates):
        tr = bar["high"] - bar["low"]
        if i:
            prev = rates[i - 1]["close"]
            tr = max(tr, abs(bar["high"] - prev), abs(bar["low"] - prev))
        if i < 14:
            total += tr
            if i == 13:
                atr = total / 14.0
        else:
            atr = (atr * 13.0 + tr) / 14.0
        if atr is not None:
            out.append(atr)
    return out


def main():
    import MetaTrader5 as mt5

    login = int(os.environ["XAUUSD_MT5_LOGIN"])
    server = os.environ["XAUUSD_MT5_SERVER"]
    ok = mt5.initialize(
        path=os.getenv("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe"),
        login=login,
        password=os.environ["XAUUSD_MT5_PASSWORD"],
        server=server,
        timeout=60000,
    )
    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "initialized": bool(ok),
        "last_error": list(mt5.last_error()),
        "order_api_called": False,
    }
    try:
        if ok:
            a = mt5.account_info()
            result["identity_match"] = bool(a and a.login == login and a.server == server)
            if a:
                result["account"] = {
                    k: getattr(a, k)
                    for k in (
                        "trade_mode",
                        "margin_mode",
                        "currency",
                        "equity",
                        "balance",
                        "margin_free",
                        "leverage",
                    )
                }
            si = mt5.symbol_info(SYMBOL)
            result["symbol_spec"] = {k: getattr(si, k) for k in SPEC_KEYS} if si else None
            tick = mt5.symbol_info_tick(SYMBOL)
            if tick:
                result["tick"] = {"time_msc": tick.time_msc, "bid": tick.bid, "ask": tick.ask}
                result["server_tick_epoch"] = int(tick.time)
                result["probe_utc_epoch"] = int(datetime.now(timezone.utc).timestamp())
            exposure = [
                {"kind": "position", "magic": p.magic}
                for p in (mt5.positions_get(symbol=SYMBOL) or ())
            ]
            exposure += [
                {"kind": "order", "magic": o.magic} for o in (mt5.orders_get(symbol=SYMBOL) or ())
            ]
            result["exposure"] = exposure
            rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M15, 1, ATR_BARS)
            if rates is not None and len(rates) > 200 and tick:
                series = wilder_atr(rates)
                atr = sorted(series[100:])
                current = series[-1]
                ladder = [
                    ("p10", atr[len(atr) // 10]),
                    ("median", atr[len(atr) // 2]),
                    ("p90", atr[len(atr) * 9 // 10]),
                    ("current", current),
                ]
                stops = []
                for label, value in ladder:
                    distance = 2.5 * value
                    loss = mt5.order_calc_profit(
                        mt5.ORDER_TYPE_BUY, SYMBOL, 1.0, tick.ask, tick.ask - distance
                    )
                    margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, SYMBOL, 1.0, tick.ask)
                    stops.append(
                        {
                            "label": label,
                            "atr": value,
                            "distance": distance,
                            "loss_1lot": None if loss is None else -loss,
                            "margin_1lot": margin,
                        }
                    )
                result["stops"] = stops
                result["stop_ladder_source"] = (
                    f"last {len(rates)} completed M15 bars; ATR seed at first fetched bar (estimate)"
                )
        dest = Path(os.environ["XAUUSD_PROBE_OUTPUT"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(result, indent=2, default=float))
        print(
            json.dumps(
                {
                    "initialized": result["initialized"],
                    "identity_match": result.get("identity_match"),
                }
            ),
            flush=True,
        )
        return 0 if result.get("identity_match") else 1
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
