"""Frozen research detector/geometry and append-only completed Bid M15 cache."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from scripts.research.reward156_search import config_id, prepare_candidate
from scripts.research.reward156_tuning import closed_h4_ema
from scripts.research.breakout_entry import prepare_entry
from scripts.research.breakout_models import Costs
from scripts.strategy import pure_b1_bars

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ID = "1af968e9ac6a26ea"
CONTRACT = {
    "strategy": "reward156",
    "formula": "archived",
    "rsi_period": 14,
    "rsi_threshold": 25,
    "sell_lookback": 96,
    "sell_ema": 50,
    "macro_span": 200,
    "buy_pause_drawdown": 0.0,
    "stop_atr": 2.5,
    "buy_stop_atr": 1.5,
    "buy_target_rr": 2.0,
    "sell_target": "atr3",
    "protect_mode": "break_even",
    "buy_protect_mode": "off",
    "daily_loss_limit": 0.1,
    "max_daily_losses": 1,
    "cooldown_bars": 0,
    "entry_session": "all",
    "risk_mode": "static",
    "risk_cap": 0.1,
}
SOURCE_PATHS = (
    "scripts/research/reward156_search.py",
    "scripts/research/reward156_tuning.py",
    "scripts/research/campaign_signals.py",
    "scripts/research/breakout_entry.py",
    "scripts/research/breakout_models.py",
    "scripts/strategy.py",
    "scripts/research/breakout_logic.py",
    "scripts/research/breakout_signals.py",
    "scripts/pure_b1/broker_data.py",
)


def verify_sources(config, *, root=ROOT):
    """Fail closed on contract or exact research source drift."""
    if (
        config_id(CONTRACT) != CONTRACT_ID
        or config.get("contract_id") != CONTRACT_ID
        or config.get("contract") != CONTRACT
    ):
        raise ValueError("source_drift")
    hashes = config.get("source_hashes", {})
    if not isinstance(hashes, dict) or set(hashes) != set(SOURCE_PATHS):
        raise ValueError("source_drift")
    try:
        if any(
            hashlib.sha256((root / path).read_bytes()).hexdigest() != hashes[path]
            for path in SOURCE_PATHS
        ):
            raise ValueError("source_drift")
    except OSError:
        raise ValueError("source_drift") from None


class BarCache:
    """Full causal prefix. Overlap must agree; never silently replace old bars."""

    def __init__(self):
        self.bars = None
        self.frame = None
        self.rules = None
        self.row = None

    def append(self, bars):
        # Canonical chronology/OHLC checks; preserve legitimate session gaps.
        pure_b1_bars(bars)
        bars = bars[["open", "high", "low", "close"]].copy()
        if self.bars is not None:
            overlap = self.bars.index.intersection(bars.index)
            if (
                overlap.empty
                or not (self.bars.loc[overlap].to_numpy() == bars.loc[overlap].to_numpy()).all()
                or not bars.loc[bars.index <= self.bars.index[-1]].index.isin(self.bars.index).all()
            ):
                raise ValueError("bar_cache_divergence")
            tail = bars.loc[bars.index > self.bars.index[-1]]
            # A sliding tail must not omit any previously sealed bar in its coverage.
            if not self.bars.loc[self.bars.index >= bars.index[0]].index.isin(bars.index).all():
                raise ValueError("bar_cache_divergence")
            if tail.empty:
                if self.row is None or pd.isna(self.row.macro_ema):
                    raise ValueError("macro_warmup_insufficient")
                return self.row
            bars = pd.concat([self.bars, tail])
        self.bars = bars
        h4_count = int((bars.close.resample("4h").count() == 16).sum())
        if h4_count < 201:
            raise ValueError("macro_warmup_insufficient")
        self.frame, self.rules = prepare_candidate(bars, CONTRACT)
        self.frame["macro_ema"] = closed_h4_ema(bars, 200)
        self.row = self.frame.iloc[-1]
        if pd.isna(self.row.macro_ema):
            raise ValueError("macro_warmup_insufficient")
        return self.row


def decide(cache, bid, ask, spec, costs, equity):
    """Return canonical EntryPlan or rejection; no broker mutations."""
    if cache.row is None or pd.isna(cache.row.macro_ema):
        return "macro_warmup_insufficient"
    if int(cache.row.direction) == 0:
        return "macro_gate" if bool(cache.row.macro_blocked) else "no_signal"
    return prepare_entry(
        cache.row,
        bid,
        ask,
        spec,
        cache.rules,
        Costs(
            slippage=costs["slippage_allowance_price"],
            commission_per_lot=costs["commission_per_lot"],
        ),
        equity,
        equity,
    )
