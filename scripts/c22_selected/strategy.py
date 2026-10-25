"""Frozen selected C22 detector/geometry adapter; no order mutation interface."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import pandas as pd

from scripts.c22h4.runner import copy_m1_rates
from scripts.demo_runtime.market_data import completed_m15_from_m1
from scripts.research.breakout_entry import prepare_entry
from scripts.research.breakout_models import Costs, Rules
from scripts.research.reward156_search import prepare_candidate
from scripts.research.reward156_tuning import closed_h4_ema
from scripts.strategy import pure_b1_bars

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_ID = "26b8bcd69e043653"
CONFIG_PATH = ROOT / "config/c22-selected-demo.json"
SNAPSHOT = "RESEARCH-C22-SELECTED-20261025-26B8"
MAGIC = 22261025
CONTRACT = {
    "strategy": "reward156", "formula": "archived", "rsi_period": 7,
    "rsi_threshold": 30, "sell_lookback": 48, "sell_ema": 50,
    "buy_ema": 50, "macro_span": 200, "buy_pause_drawdown": 0.0,
    "stop_atr": 2.5, "buy_stop_atr": 2.5, "buy_target_rr": 3.0,
    "sell_target": "r1.35", "protect_mode": "break_even",
    "buy_protect_mode": "break_even", "daily_loss_limit": 0.1,
    "max_daily_losses": 2, "cooldown_bars": 2, "entry_session": "all",
    "risk_mode": "static", "risk_cap": 0.1,
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
    "scripts/demo_runtime/market_data.py",
    "scripts/c22h4/runner.py",
    "scripts/c22_selected/__init__.py",
    "scripts/c22_selected/strategy.py",
    "scripts/c22_selected/runner.py",
    "scripts/c22_selected/__main__.py",
    "scripts/c22_selected/execution.py",
    "scripts/c22_selected/trial_costs.py",
    "scripts/ops/mt5_wine_c22_selected.py",
)


def _rules_id(rules: Rules) -> str:
    return hashlib.sha256(json.dumps(asdict(rules), sort_keys=True).encode()).hexdigest()[:16]


def verify_sources(config: dict, *, root: Path = ROOT) -> None:
    """Bind exact selected recipe and adapter sources without rewriting archives."""
    if not isinstance(config, dict):
        raise ValueError("source_drift")
    if (
        config.get("snapshot") != SNAPSHOT
        or config.get("contract_id") != CANDIDATE_ID
        or config.get("contract") != CONTRACT
        or config.get("symbol") != "XAUUSDm"
        or config.get("volume") != 0.01
        or config.get("real_money") != "PROHIBITED"
    ):
        raise ValueError("source_drift")
    hashes = config.get("source_hashes")
    if not isinstance(hashes, dict) or set(hashes) != set(SOURCE_PATHS):
        raise ValueError("source_drift")
    try:
        if any(hashlib.sha256((root / path).read_bytes()).hexdigest() != hashes[path] for path in SOURCE_PATHS):
            raise ValueError("source_drift")
    except OSError:
        raise ValueError("source_drift") from None


class SelectedBarCache:
    """Causal Bid M15 prefix; frozen old Demo cache remains untouched."""

    def __init__(self):
        self.bars = None
        self.frame = None
        self.rules = None
        self.row = None

    def append(self, bars):
        pure_b1_bars(bars)
        bars = bars[["open", "high", "low", "close"]].copy()
        if self.bars is not None:
            overlap = self.bars.index.intersection(bars.index)
            if (
                overlap.empty
                or not (self.bars.loc[overlap].to_numpy() == bars.loc[overlap].to_numpy()).all()
                or not bars.loc[bars.index <= self.bars.index[-1]].index.isin(self.bars.index).all()
                or not self.bars.loc[self.bars.index >= bars.index[0]].index.isin(bars.index).all()
            ):
                raise ValueError("bar_cache_divergence")
            tail = bars.loc[bars.index > self.bars.index[-1]]
            if tail.empty:
                if self.row is None or pd.isna(self.row.macro_ema):
                    raise ValueError("macro_warmup_insufficient")
                return self.row
            bars = pd.concat([self.bars, tail])
        self.bars = bars
        if int((bars.close.resample("4h").count() == 16).sum()) < 201:
            raise ValueError("macro_warmup_insufficient")
        self.frame, self.rules = prepare_candidate(bars, CONTRACT)
        if _rules_id(self.rules) != CANDIDATE_ID:
            raise ValueError("selected_rules_drift")
        self.frame["macro_ema"] = closed_h4_ema(bars, 200)
        self.row = self.frame.iloc[-1]
        if pd.isna(self.row.macro_ema):
            raise ValueError("macro_warmup_insufficient")
        return self.row


def decide(cache, bid, ask, spec, costs, equity):
    """Canonical frozen price and cost-inclusive initial risk calculation."""
    if cache.row is None or pd.isna(cache.row.macro_ema):
        return "macro_warmup_insufficient"
    if cache.rules is None or _rules_id(cache.rules) != CANDIDATE_ID:
        return "selected_rules_drift"
    if int(cache.row.direction) == 0:
        return "macro_gate" if bool(cache.row.macro_blocked) else "no_signal"
    return prepare_entry(
        cache.row, bid, ask, spec, cache.rules,
        Costs(slippage=costs["slippage_allowance_price"], commission_per_lot=costs["commission_per_lot"]),
        equity, equity,
    )


class SelectedStrategy:
    snapshot = SNAPSHOT
    magic = MAGIC
    prefix = "C22_"
    allowed_sides = (-1, 1)
    daily_loss_limit = 0.1
    risk_cap = 0.1
    max_daily_losses = 2
    cooldown_bars = 2
    no_signal_reason = "no_signal"

    def __init__(self, config):
        self.config = config
        self.cache = SelectedBarCache()
        self.source_error = None
        try:
            verify_sources(config)
        except ValueError as exc:
            self.source_error = str(exc)

    def frame(self, bars, mt5, symbol, now):
        if self.source_error:
            raise ValueError(self.source_error)
        verify_sources(self.config)
        if self.cache.bars is None:
            started = time.monotonic()
            bars = completed_m15_from_m1(copy_m1_rates(mt5, symbol), now=now)
            if time.monotonic() - started >= 60:
                raise ValueError("history_bootstrap_timeout")
        try:
            self.cache.append(bars)
        except ValueError as exc:
            if str(exc) == "bar_cache_divergence":
                self.cache = SelectedBarCache()
            raise
        row = self.cache.row
        if row is None or self.cache.frame is None:
            raise ValueError("macro_warmup_insufficient")
        self.no_signal_reason = "macro_gate" if bool(row.macro_blocked) else "no_signal"
        return self.cache.frame

    def levels(self, row, tick, info, costs, account):
        spec = {
            key: float(getattr(info, key))
            for key in ("trade_tick_size", "trade_contract_size", "volume_min", "volume_max", "volume_step")
        }
        spec["leverage"] = float(account.leverage)
        plan = decide(self.cache, float(tick.bid), float(tick.ask), spec, costs, float(account.equity))
        if isinstance(plan, str):
            raise ValueError(plan)
        return plan.entry, plan.stop, plan.target

    def protects(self, direction):
        return direction in self.allowed_sides

    def diagnostics(self):
        row = self.cache.row
        bars = self.cache.bars
        if row is None or bars is None:
            return {}
        return {
            "candidate_id": CANDIDATE_ID,
            "macro_ema": float(row.macro_ema) if row.notna()["macro_ema"] else None,
            "cache_bars": len(bars),
        }

    def entry_thesis(self):
        row = self.cache.row
        if row is None or int(row.direction) == 0:
            return None
        buy = int(row.direction) == 1
        return {
            "side": "BUY" if buy else "SELL", "close": float(row.close),
            "macro_ema": float(row.macro_ema), "atr": float(row.atr),
            "prior_low": None if buy else float(row.ll),
            "why": (
                "Selected26b8: RSI7 crosses30 / EMA50 / closed H4 EMA200; BUY SL2.5ATR TP3R BE1R"
                if buy else
                "Selected26b8: prior48-bar breakout / EMA50 / closed H4 EMA200; SELL SL2.5ATR TP1.35R BE1R"
            ),
        }
