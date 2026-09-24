"""Frozen GOLD_V2_DEMO profile shared by backtest and Demo live."""

from __future__ import annotations

from typing import Any

import pandas as pd

from scripts.smc.eval_windows import label_foundation_window


GOLD_V2_DEMO: dict[str, Any] = {
    "risk_pct": 0.005,
    "max_sl_cap": 25.0,
    "tp_r": 2.5,
    "partial_tp_enabled": True,
    "partial_tp_r": 1.0,
    "partial_tp_ratio": 0.5,
    "be_buffer": 0.10,
    "extended_killzones": True,
    "require_choch": True,
    "min_body_ratio": 0.45,
    "max_sweep_pierce": 8.0,
    "sweep_lookback": 25,
    "max_sweep_to_mss_bars": 8,
    "max_mss_to_fvg_bars": 4,
    "spread_buffer": 0.30,
    "contract_size": 100.0,
    "symbol": "XAUUSDm",
    "min_split_lot": 0.02,
    "ttl_expire_bars": 4,
    "bar_minutes": 5,
    "max_spread": 0.35,
    "source_label": "exness_xauusdm",
}


def slice_m5_window(df: pd.DataFrame, window_name: str) -> pd.DataFrame:
    """Keep only M5 bars whose foundation label matches window_name."""
    if df.empty:
        return df.copy()
    mask = df["time"].map(lambda ts: label_foundation_window(ts).name == window_name)
    return df.loc[mask].reset_index(drop=True)


def count_split_eligible(lot_sizes) -> tuple[int, int]:
    """Return (eligible_two_tier, full_ticket_only) from trade lot sizes."""
    eligible = 0
    full_only = 0
    min_lot = float(GOLD_V2_DEMO["min_split_lot"])
    for lot in lot_sizes:
        if float(lot) + 1e-9 >= min_lot:
            eligible += 1
        else:
            full_only += 1
    return eligible, full_only
