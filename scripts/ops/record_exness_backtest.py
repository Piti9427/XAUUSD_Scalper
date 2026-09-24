#!/usr/bin/env python3
"""Run GOLD_V2_DEMO backtests per foundation window and write the ops artifact."""

from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.run_backtest import load_csv  # noqa: E402
from scripts.smc.backtester import SMCBacktester, format_backtest_summary  # noqa: E402
from scripts.smc.gold_v2_demo import GOLD_V2_DEMO, count_split_eligible, slice_m5_window  # noqa: E402


WINDOWS = ("development", "holdout", "out_of_range")


def _metrics(summary) -> dict:
    trades = summary.trades_df
    provenance = summary.provenance
    wilson = summary.wilson
    replay = summary.replay_report
    cost = summary.cost_report
    lots = []
    if trades is not None and not getattr(trades, "empty", True):
        lots = [float(x) for x in trades["lot_size"].tolist()]
    split_ok, full_only = count_split_eligible(lots)
    return {
        "initial_balance": summary.initial_balance,
        "final_balance": summary.final_balance,
        "net_profit": summary.net_profit,
        "total_trades": summary.total_trades,
        "winning_trades": summary.winning_trades,
        "losing_trades": summary.losing_trades,
        "be_trades": summary.be_trades,
        "win_rate": summary.win_rate,
        "profit_factor": summary.profit_factor,
        "max_drawdown_pct": summary.max_drawdown_pct,
        "avg_r": summary.avg_r,
        "sample_verdict": summary.sample_verdict,
        "eval_window": summary.eval_window,
        "provenance_code": getattr(provenance, "code", None),
        "provenance_ok": getattr(provenance, "ok", None),
        "wilson": None
        if wilson is None
        else {"n": wilson.n, "wins": wilson.wins, "lower": wilson.lower, "upper": wilson.upper},
        "replay_kind": getattr(getattr(replay, "kind", None), "value", None),
        "funnel": summary.funnel,
        "two_tier_eligible": split_ok,
        "full_ticket_only": full_only,
        "trade_log": json.loads(trades.to_json(orient="records", date_format="iso"))
        if trades is not None and not getattr(trades, "empty", True)
        else [],
        "cost_net_operating": getattr(cost, "net_operating_profit", None),
    }


def main() -> int:
    meta_path = ROOT / "data/exness-demo/export_meta.json"
    m5_path = ROOT / "data/exness-demo/XAUUSDm_M5.csv"
    h1_path = ROOT / "data/exness-demo/XAUUSDm_H1.csv"
    if not m5_path.is_file() or not h1_path.is_file() or not meta_path.is_file():
        print("DATA_INSUFFICIENT: missing exness-demo export")
        return 1
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if (
        meta.get("symbol") != GOLD_V2_DEMO["symbol"]
        or "exness" not in str(meta.get("server") or "").lower()
    ):
        print("DATA_INSUFFICIENT: export broker/symbol identity mismatch")
        return 1
    balance = float(meta.get("balance") or 0.0)
    if balance <= 0:
        print("DATA_INSUFFICIENT: export balance missing")
        return 1
    df_m5 = load_csv(str(m5_path))
    df_h1 = load_csv(str(h1_path))
    results = {
        "server": meta.get("server"),
        "symbol": meta.get("symbol"),
        "m5_sha256": hashlib.sha256(m5_path.read_bytes()).hexdigest(),
        "h1_sha256": hashlib.sha256(h1_path.read_bytes()).hexdigest(),
        "balance": balance,
        "clock": meta.get("clock"),
        "m5_bars_export": meta.get("m5_bars"),
        "h1_bars_export": meta.get("h1_bars"),
        "m5_start": meta.get("m5_start"),
        "m5_end": meta.get("m5_end"),
        "h1_warmup_ok": meta.get("h1_warmup_ok"),
        "profile": GOLD_V2_DEMO,
        "adr_0025": "INCONCLUSIVE",
        "windows": {},
    }
    lines = [
        "# SMC Exness XAUUSDm backtest — 2026-09-21",
        "",
        "GOLD_V2_DEMO on broker M5/H1 from Wine `copy_rates`. Not HISTORICAL_QUALIFIED. ADR-0025 remains INCONCLUSIVE.",
        "",
        f"- Demo account: `[REDACTED_ID]` / `{meta.get('server')}` / `{meta.get('symbol')}`",
        f"- Balance snapshot: ${balance:,.2f}",
        f"- Clock: `{meta.get('clock')}` last closed M5 `{meta.get('m5_end')}` tick `{meta.get('tick_time')}`",
        f"- Export: M5 `{meta.get('m5_bars')}` bars `{meta.get('m5_start')}` → `{meta.get('m5_end')}` ({meta.get('m5_method')})",
        f"- H1: `{meta.get('h1_bars')}` bars warmup_ok={meta.get('h1_warmup_ok')}",
        "- Ticks: none → provenance `DATA_OHLC_ONLY` (dual-touch stays AMBIGUOUS)",
        "- Two-tier needs lot ≥ 0.02; smaller lots keep full SL/TP",
        "",
    ]
    for window in WINDOWS:
        sliced = slice_m5_window(df_m5, window)
        print(f"WINDOW {window} bars={len(sliced)}", flush=True)
        if sliced.empty:
            results["windows"][window] = {"empty": True, "sample_verdict": "DATA_INSUFFICIENT"}
            lines.append(f"## {window}")
            lines.append("")
            lines.append("DATA_INSUFFICIENT: no M5 bars in this window.")
            lines.append("")
            continue
        bt = SMCBacktester(
            initial_balance=balance,
            risk_pct=GOLD_V2_DEMO["risk_pct"],
            spread_buffer=GOLD_V2_DEMO["spread_buffer"],
            max_sl_cap=GOLD_V2_DEMO["max_sl_cap"],
            contract_size=GOLD_V2_DEMO["contract_size"],
            partial_tp_enabled=GOLD_V2_DEMO["partial_tp_enabled"],
            partial_tp_r=GOLD_V2_DEMO["partial_tp_r"],
            partial_tp_ratio=GOLD_V2_DEMO["partial_tp_ratio"],
            be_trigger_r=1.0,
            extended_killzones=GOLD_V2_DEMO["extended_killzones"],
            tp_r=GOLD_V2_DEMO["tp_r"],
            min_body_ratio=GOLD_V2_DEMO["min_body_ratio"],
            max_sweep_pierce=GOLD_V2_DEMO["max_sweep_pierce"],
            sweep_lookback=GOLD_V2_DEMO["sweep_lookback"],
            max_sweep_to_mss_bars=GOLD_V2_DEMO["max_sweep_to_mss_bars"],
            max_mss_to_fvg_bars=GOLD_V2_DEMO["max_mss_to_fvg_bars"],
            require_choch=GOLD_V2_DEMO["require_choch"],
            is_proxy_feed=False,
            source_label=GOLD_V2_DEMO["source_label"],
        )
        summary = bt.run(sliced, df_h1)
        block = _metrics(summary)
        block["m5_bars"] = int(len(sliced))
        block["m5_start"] = str(sliced["time"].iloc[0])
        block["m5_end"] = str(sliced["time"].iloc[-1])
        if window == "out_of_range":
            block["gate_d_note"] = "not a Gate D sample"
        results["windows"][window] = block
        lines.append(f"## {window}")
        lines.append("")
        if window == "out_of_range":
            lines.append("Forward snapshot after foundation dataset end. Not a Gate D sample.")
            lines.append("")
        lines.append(format_backtest_summary(summary).strip())
        lines.append("")
        lines.append(
            f"Two-tier eligible (>=0.02 lot): {block['two_tier_eligible']}; "
            f"full-ticket only: {block['full_ticket_only']}"
        )
        lines.append("")
        if block["trade_log"]:
            lines.append("Trade log:")
            lines.append("")
            for row in block["trade_log"]:
                lines.append(
                    f"- {row.get('entry_time')} {row.get('direction')} lot={row.get('lot_size')} "
                    f"entry={row.get('entry_price')} sl={row.get('sl_price')} "
                    f"exit={row.get('exit_reason')} pnl={row.get('pnl_dollar')}"
                )
            lines.append("")
        print(
            f"WINDOW {window} trades={summary.total_trades} verdict={summary.sample_verdict} "
            f"net={summary.net_profit}",
            flush=True,
        )

    docs = ROOT / "docs/ops/2026-09-21-smc-exness-backtest.md"
    json_path = ROOT / "docs/ops/2026-09-21-smc-exness-backtest.json"
    docs.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"wrote {docs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
