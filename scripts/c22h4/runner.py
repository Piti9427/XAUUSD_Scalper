"""Candidate hooks on verified shared Demo broker lifecycle; research only."""

from __future__ import annotations

import json
import time

from scripts.c22h4.strategy import BarCache, ROOT, decide, verify_sources
from scripts.pure_b1.broker_data import completed_m15_from_m1
from scripts.trial30.runner import Trial30DemoRunner

SNAPSHOT = "RESEARCH-C22-H4EMA200-20261004"
MAGIC = 22261004


class C22H4Strategy:
    snapshot = SNAPSHOT
    magic = MAGIC
    prefix = "C22_"
    allowed_sides = (-1, 1)
    daily_loss_limit = 0.10
    risk_cap = 0.10
    max_daily_losses = 1
    no_signal_reason = "no_signal"

    def __init__(self, config):
        self.config = config
        self.cache = BarCache()
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
            bars = completed_m15_from_m1(
                mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 100000), now=now
            )
            if time.monotonic() - started >= 60:
                raise ValueError("history_bootstrap_timeout")
        try:
            self.cache.append(bars)
        except ValueError as exc:
            if str(exc) == "bar_cache_divergence":
                self.cache = BarCache()  # block this cycle; rebuild from broker next cycle
            raise
        self.no_signal_reason = "macro_gate" if bool(self.cache.row.macro_blocked) else "no_signal"
        return self.cache.frame

    def levels(self, row, tick, info, costs, account):
        spec = {
            key: float(getattr(info, key))
            for key in (
                "trade_tick_size",
                "trade_contract_size",
                "volume_min",
                "volume_max",
                "volume_step",
            )
        }
        spec["leverage"] = float(account.leverage)
        plan = decide(
            self.cache, float(tick.bid), float(tick.ask), spec, costs, float(account.equity)
        )
        if isinstance(plan, str):
            raise ValueError(plan)
        return plan.entry, plan.stop, plan.target

    def protects(self, direction):
        return direction == -1

    def diagnostics(self):
        row = self.cache.row
        if row is None:
            return {}
        return dict(
            macro_ema=float(row.macro_ema) if row.notna()["macro_ema"] else None,
            cache_bars=len(self.cache.bars),
        )


class C22H4DemoRunner(Trial30DemoRunner):
    def __init__(self, *, config=None, **kwargs):
        config = (
            json.loads((ROOT / "config/c22h4-demo.json").read_text()) if config is None else config
        )
        super().__init__(strategy=C22H4Strategy(config), **kwargs)

    def export_cache(self, path):
        """Persist exact causal prefix for shadow audit, only when last bar changes."""
        if self.strategy.cache.bars is None:
            return
        last = self.strategy.cache.bars.index[-1]
        if getattr(self, "_exported_bar", None) == last:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_suffix(".pending")
        self.strategy.cache.bars.to_csv(pending)
        pending.replace(path)
        self._exported_bar = last
