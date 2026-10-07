"""Candidate hooks on verified shared Demo broker lifecycle; research only."""

from __future__ import annotations

import json
from pathlib import Path
import time

from scripts.c22h4.strategy import BarCache, ROOT, decide, verify_sources
from scripts.c22h4.trade_log import (
    append_note,
    render_block,
    render_entry,
    render_exit,
    review_exit,
)
from scripts.pure_b1.broker_data import completed_m15_from_m1
from scripts.trial30.runner import Trial30DemoRunner

SNAPSHOT = "RESEARCH-C22-H4EMA200-20261004"
MAGIC = 22261004
BOOTSTRAP_M1 = 100000
M1_PAGE = 50000


def copy_m1_rates(mt5, symbol, count=BOOTSTRAP_M1, *, page=M1_PAGE):
    """Copy M1 bars without a single request equal to terminal MaxBars."""
    if count <= 0 or page <= 0:
        raise ValueError("missing M1 bars")
    chunks = []
    fetched = 0
    while fetched < count:
        n = min(page, count - fetched)
        part = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, fetched, n)
        if part is None or len(part) == 0:
            raise ValueError("missing M1 bars")
        chunks.append(part)
        fetched += len(part)
        if len(part) < n:
            break
    ordered = list(reversed(chunks))
    for older, newer in zip(ordered, ordered[1:]):
        if int(older[-1]["time"]) >= int(newer[0]["time"]):
            raise ValueError("duplicate or unordered M1 bars")
    first = ordered[0]
    if hasattr(first, "dtype") and getattr(first.dtype, "names", None):
        import numpy as np

        return np.concatenate(ordered)
    out = []
    for part in ordered:
        out.extend(part)
    return out


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
            bars = completed_m15_from_m1(copy_m1_rates(mt5, symbol), now=now)
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

    def entry_thesis(self):
        """Prices and frozen rule text for the trade note. No new signal math."""
        row = self.cache.row
        if row is None or int(row.direction) == 0:
            return None
        side = "BUY" if int(row.direction) == 1 else "SELL"
        close = float(row.close)
        macro = float(row.macro_ema)
        atr = float(row.atr) if "atr" in row.index and row.notna()["atr"] else None
        prior_low = (
            float(row.ll) if side == "SELL" and "ll" in row.index and row.notna()["ll"] else None
        )
        if side == "BUY":
            why = (
                "สัญญาณ BUY ตามสัญญาที่ล็อก: RSI14 ตัดขึ้นผ่าน 25, แท่งปิดบวก, "
                "ปิดเหนือ EMA50 และ EMA50 สูงกว่า 4 แท่งก่อน, "
                f"ราคาปิด {close:.3f} อยู่เหนือ H4 EMA200 {macro:.3f}"
            )
        else:
            low_text = f"{prior_low:.3f}" if prior_low is not None else "ไม่มี"
            why = (
                "สัญญาณ SELL ตามสัญญาที่ล็อก: ปิดต่ำกว่า prior 96 แท่ง, "
                "ปิดต่ำกว่า EMA50 และ EMA50 ต่ำกว่า 4 แท่งก่อน, "
                f"ราคาปิด {close:.3f} ต่ำกว่า low ก่อนหน้า {low_text} "
                f"และต่ำกว่า H4 EMA200 {macro:.3f}"
            )
        return dict(side=side, close=close, macro_ema=macro, atr=atr, prior_low=prior_low, why=why)


class C22H4DemoRunner(Trial30DemoRunner):
    def __init__(self, *, config=None, **kwargs):
        config = (
            json.loads((ROOT / "config/c22h4-demo.json").read_text()) if config is None else config
        )
        journal_path = Path(kwargs["journal_path"])
        self.trade_log_path = journal_path.with_name(journal_path.stem + "-trades.md")
        super().__init__(strategy=C22H4Strategy(config), **kwargs)
        self.broker.restart_unknown_baseline = True

    def cycle(self, *, now):
        prior = self.journal.get("active")
        result = super().cycle(now=now)
        self._record_trade_note(prior, result, now)
        return result

    def _record_trade_note(self, prior, result, now):
        status = result.get("status")
        if status == "BLOCKED":
            reason = str(result.get("reason") or "")
            key = now.date().isoformat() + "|" + reason
            if self.journal.get("trade_block_note") == key:
                return
            title, body, record = render_block(now.isoformat(), reason)
            append_note(self.trade_log_path, title, body, record)
            self.journal.put("trade_block_note", key)
            return
        active = self.journal.get("active") if status == "FILLED" else prior
        if not isinstance(active, dict) or not active.get("thesis"):
            return
        thesis = active["thesis"]
        request = active.get("request") or {}
        fill = float(active.get("fill") or request.get("price") or 0)
        stop = float(request.get("sl") or 0)
        target = float(request.get("tp") or 0)
        if status == "FILLED":
            if active.get("entry_noted"):
                return
            title, body, record = render_entry(now.isoformat(), thesis, fill, stop, target)
            append_note(self.trade_log_path, title, body, record)
            active["entry_noted"] = True
            self.journal.put("active", active)
            return
        if status not in ("CLOSED", "SAFETY_CLOSED"):
            return
        review = review_exit(
            side=thesis.get("side") or "",
            fill=fill,
            stop=stop,
            target=target,
            exit_price=result.get("exit_price"),
            net=float(result.get("net") or 0),
            profit=float(result.get("profit") or 0),
            commission=float(result.get("commission") or 0),
            swap=float(result.get("swap") or 0),
            fee=float(result.get("fee") or 0),
            safety_reason=result.get("reason") if status == "SAFETY_CLOSED" else None,
        )
        title, body, record = render_exit(
            now.isoformat(),
            thesis,
            review,
            side=thesis.get("side"),
            fill=fill,
            exit_price=result.get("exit_price"),
            net=result.get("net"),
        )
        append_note(self.trade_log_path, title, body, record)

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
