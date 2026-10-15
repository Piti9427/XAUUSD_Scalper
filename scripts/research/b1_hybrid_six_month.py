"""Offline two-leg B1/MSS reconstruction on verified Exness Bid/Ask ticks."""

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .b1_final import normalize_price, reference_bars
from .feedback_round import directions


@dataclass
class Leg:
    direction: int
    entry: float
    stop: float
    target: float
    volume: float
    entry_index: int
    entry_roll: float
    fee: float
    label: str


class Replay:
    def __init__(
        self,
        times,
        bid,
        ask,
        broker,
        *,
        cost_scenario,
        apply_swap=None,
        entry_fee_r=None,
        entry_stress_price=0.0,
        day_quota_limit=99,
        signal_day_start=True,
        boundary_day_start_only=False,
        tick_rounder=None,
        stop_atr=2.5,
        target_atr=6.25,
    ):
        self.times, self.bid, self.ask = times, bid, ask
        self.broker = broker
        self.cost_scenario = cost_scenario
        self.swap_enabled = cost_scenario if apply_swap is None else bool(apply_swap)
        self.entry_fee_r = (0.1 if cost_scenario else 0.0) if entry_fee_r is None else float(entry_fee_r)
        self.entry_stress_price = float(entry_stress_price)
        self.day_quota_limit = day_quota_limit
        self.signal_day_start = signal_day_start
        self.boundary_day_start_only = boundary_day_start_only
        self.tick_rounder = tick_rounder
        self.stop_atr = float(stop_atr)
        self.target_atr = float(target_atr)
        if self.stop_atr <= 0 or self.target_atr <= 0:
            raise ValueError("stop and target ATR multipliers must be positive")
        self.balance = self.peak = 200.0
        self.max_dd = 0.0
        self.halted = False
        self.legs = []
        self.basket_start = self.basket_budget = None
        self.basket_open_index = None
        self.basket_count = 0
        self.recovery_count = 0
        self.basket_had_recovery = False
        self.basket_rows, self.leg_rows = [], []
        self.day_start, self.day_quota = {}, {}
        self.rejections = {
            "daily_loss": 0,
            "daily_quota": 0,
            "hwm_halt": 0,
            "margin_proxy": 0,
            "tick_gap": 0,
            "recovery_not_negative": 0,
            "day_start_unknown": 0,
            "late_quote": 0,
        }
        self.close_reasons = {}
        self.grid = broker["trade_tick_size"]
        self.contract = broker["trade_contract_size"]
        self.leverage = broker["leverage"]
        self.swap_unit = (broker["swap_long"], broker["swap_short"])
        first = pd.Timestamp(int(times[0]), unit="ms", tz="UTC").normalize()
        last = pd.Timestamp(int(times[-1]), unit="ms", tz="UTC").normalize()
        days = pd.date_range(first + pd.Timedelta(days=1), last, freq="D")
        self.roll_millis = np.array([d.value // 10**6 for d in days], dtype=np.int64)
        weights = np.array(
            [3 if d.dayofweek + 1 == broker["swap_rollover3days"] else 1 for d in days], dtype=float
        )
        self.roll_acc = np.r_[0.0, np.cumsum(weights)]

    def _rolls(self, times):
        return self.roll_acc[np.searchsorted(self.roll_millis, times, side="right")]

    def _round(self, price, direction):
        if self.tick_rounder is None:
            return normalize_price(price, self.grid)
        return self.tick_rounder(price, self.grid, direction)

    def _swaps(self, leg, times):
        if not self.swap_enabled or self.broker["swap_mode"] != 1:
            return 0.0
        points = self.broker["swap_long"] if leg.direction == 1 else self.broker["swap_short"]
        return (
            (self._rolls(times) - leg.entry_roll)
            * points
            * self.broker["point"]
            * self.contract
            * leg.volume
        )

    def _pnl(self, leg, left, right):
        quote = self.bid[left:right] if leg.direction == 1 else self.ask[left:right]
        return leg.direction * (quote - leg.entry) * self.contract * leg.volume + self._swaps(
            leg, self.times[left:right]
        )

    def equity_at(self, index):
        return self.balance + sum(float(self._pnl(leg, index, index + 1)[0]) for leg in self.legs)

    def _observe(self, marks, ticks):
        if len(marks) == 0:
            return
        peaks = np.maximum.accumulate(np.r_[self.peak, marks])[1:]
        self.max_dd = max(self.max_dd, float(np.max((peaks - marks) / peaks)))
        self.peak = max(self.peak, float(np.max(marks)))
        days = ticks // 86400000
        firsts = np.r_[0, np.flatnonzero(np.diff(days)) + 1]
        for n in firsts:
            day = int(days[n])
            if self.boundary_day_start_only:
                stamp = pd.Timestamp(int(ticks[n]), unit="ms", tz="UTC")
                if stamp.hour or stamp.minute or stamp.second:
                    continue
            self.day_start.setdefault(day, float(marks[n]))

    def _settle(self, leg, index, reason):
        bid_or_ask = float(self.bid[index] if leg.direction == 1 else self.ask[index])
        exit_price = leg.target if reason == "TP" else bid_or_ask
        gross = leg.direction * (exit_price - leg.entry) * self.contract * leg.volume
        swap = (
            float(self._swaps(leg, self.times[index : index + 1])[0]) if self.swap_enabled else 0.0
        )
        net_after_entry_fee = gross + swap - leg.fee
        self.balance += gross + swap
        self.leg_rows.append(
            {
                "basket": self.basket_count,
                "leg": leg.label,
                "entry_time_utc": str(
                    pd.Timestamp(int(self.times[leg.entry_index]), unit="ms", tz="UTC")
                ),
                "exit_time_utc": str(pd.Timestamp(int(self.times[index]), unit="ms", tz="UTC")),
                "direction": leg.direction,
                "volume": leg.volume,
                "entry": leg.entry,
                "stop": leg.stop,
                "target": leg.target,
                "exit": exit_price,
                "gross": gross,
                "swap_scenario": swap,
                "entry_fee_scenario": leg.fee,
                "net": net_after_entry_fee,
                "reason": reason,
            }
        )
        self.legs.remove(leg)

    def _close_basket(self, index, reason):
        for leg in self.legs[:]:
            self._settle(leg, index, reason)
        net = self.balance - self.basket_start
        self.basket_rows.append(
            {
                "basket": self.basket_count,
                "open_time_utc": str(
                    pd.Timestamp(int(self.times[self.basket_open_index]), unit="ms", tz="UTC")
                ),
                "close_time_utc": str(pd.Timestamp(int(self.times[index]), unit="ms", tz="UTC")),
                "budget_usd": self.basket_budget,
                "net": net,
                "balance": self.balance,
                "reason": reason,
                "leg_count": len([r for r in self.leg_rows if r["basket"] == self.basket_count]),
            }
        )
        self.close_reasons[reason] = self.close_reasons.get(reason, 0) + 1
        self.basket_start = self.basket_budget = self.basket_open_index = None
        self.basket_had_recovery = False
        if reason == "HWM_HALT" or self.balance <= self.peak * 0.0:
            self.halted = True

    def _open(self, index, direction, atr, volume, label):
        entry = float(self.ask[index] if direction == 1 else self.bid[index])
        entry += direction * self.entry_stress_price
        stop = self._round(entry - direction * atr * self.stop_atr, direction)
        distance = abs(entry - stop)
        if not np.isfinite(distance) or distance <= 0:
            return False
        target = self._round(entry + direction * atr * self.target_atr, direction)
        fee = self.entry_fee_r * distance * self.contract * volume
        # --- 10% Risk Cap: reject if SL risk > 10% of current equity ---
        risk_usd = distance * self.contract * volume
        equity = self.equity_at(index)
        if equity > 0 and risk_usd > equity * 0.10:
            self.rejections["margin_proxy"] += 1
            return False
        new_margin = (
            entry * self.contract * (sum(leg.volume for leg in self.legs) + volume) / self.leverage
        )
        if equity - fee <= new_margin:
            self.rejections["margin_proxy"] += 1
            return False
        if not (self.broker["volume_min"] <= volume <= self.broker["volume_max"]):
            raise ValueError("fixed lot outside broker min/max")
        if not np.isclose(
            volume / self.broker["volume_step"], round(volume / self.broker["volume_step"])
        ):
            raise ValueError("fixed lot not on broker step")
        self.balance -= fee
        self.legs.append(
            Leg(
                direction,
                entry,
                stop,
                target,
                volume,
                index,
                float(self._rolls(self.times[index : index + 1])[0]),
                fee,
                label,
            )
        )
        return True

    def on_signal(self, index, b1, recovery, atr):
        day = int(self.times[index] // 86400000)
        equity = self.equity_at(index)
        if self.signal_day_start:
            self.day_start.setdefault(day, equity)
        if day not in self.day_start:
            self.rejections["day_start_unknown"] += 1
            return
        if self.halted or equity <= self.peak * 0.0:
            self.halted = True
            self.rejections["hwm_halt"] += 1
            return
        if not self.legs:
            if not b1:
                return
            if self.day_start[day] - equity >= self.day_start[day] * 0.40:
                self.rejections["daily_loss"] += 1
                return
            if self.day_quota_limit is not None and self.day_quota.get(day, 0) >= self.day_quota_limit:
                self.rejections["daily_quota"] += 1
                return
            self.basket_start = self.balance
            self.basket_budget = 999.0
            if self._open(index, int(b1), float(atr), 0.01, "entry"):
                self.basket_count += 1
                self.basket_open_index = index
                self.basket_had_recovery = False
                if self.day_quota_limit is not None:
                    self.day_quota[day] = self.day_quota.get(day, 0) + 1
            else:
                self.basket_start = self.basket_budget = None
            return
        if not recovery or len(self.legs) >= 1:
            return
        if int(recovery) != self.legs[0].direction:
            return
        if equity - self.basket_start >= 0:
            self.rejections["recovery_not_negative"] += 1
            return
        if equity - self.basket_start <= -self.basket_budget:
            return
        if self._open(index, int(recovery), float(atr), 0.02, "recovery"):
            self.recovery_count += 1
            self.basket_had_recovery = True

    def advance(self, start, end):
        cursor = start
        while self.legs and cursor < end:
            right = min(cursor + 100000, end)
            ticks = self.times[cursor:right]
            pnl = np.zeros(right - cursor)
            individual = []
            for leg in self.legs:
                pnl += self._pnl(leg, cursor, right)
                quote = self.bid[cursor:right] if leg.direction == 1 else self.ask[cursor:right]
                individual.append(
                    (
                        leg.direction * (quote - leg.stop) <= 0,
                        leg.direction * (quote - leg.target) >= 0,
                    )
                )
            marks = self.balance + pnl
            peaks = np.maximum.accumulate(np.r_[self.peak, marks])[1:]
            cap_hit = marks - self.basket_start <= -self.basket_budget
            hwm_hit = marks <= peaks * 0.0
            tp_hit = (
                marks > self.basket_start
                if self.basket_had_recovery
                else np.zeros(len(marks), dtype=bool)
            )
            any_individual = np.zeros(len(marks), dtype=bool)
            for sl, tp in individual:
                any_individual |= sl | tp
            hits = np.flatnonzero(cap_hit | hwm_hit | tp_hit | any_individual | (marks <= 0))
            used = int(hits[0]) + 1 if len(hits) else len(marks)
            self._observe(marks[:used], ticks[:used])
            if not len(hits):
                cursor = right
                continue
            n = used - 1
            index = cursor + n
            if hwm_hit[n] or marks[n] <= 0:
                self._close_basket(index, "HWM_HALT")
            elif cap_hit[n]:
                self._close_basket(index, "BASKET_SL")
            elif tp_hit[n]:
                self._close_basket(index, "BASKET_TP")
            else:
                for leg, (sl, tp) in zip(self.legs[:], individual):
                    if sl[n] or tp[n]:
                        self._settle(leg, index, "SL" if sl[n] else "TP")
                if not self.legs:
                    self._close_basket(index, "LEG_EXIT")
                elif self.equity_at(index) - self.basket_start <= -self.basket_budget:
                    self._close_basket(index, "BASKET_SL")
            cursor = index + 1


def run(baseline, capture_dir, output, recovery_rule, cost_scenario):
    meta = json.loads((baseline / "manifest.json").read_text())
    if not (baseline / "COMPLETE").exists():
        raise ValueError("baseline incomplete")
    for name, digest in meta["artifacts_sha256"].items():
        if hashlib.sha256((baseline / name).read_bytes()).hexdigest() != digest:
            raise ValueError("baseline hash mismatch: " + name)
    capture = json.loads((capture_dir / "manifest.json").read_text())
    if (
        hashlib.sha256((capture_dir / "manifest.json").read_bytes()).hexdigest()
        != meta["capture_manifest_sha256"]
    ):
        raise ValueError("capture/baseline mismatch")
    broker = dict(capture["symbol_spec"], leverage=capture["account"]["leverage"])
    if capture["account"]["currency"] != "USD" or capture["symbol"] != "XAUUSDm":
        raise ValueError("broker identity mismatch")
    raw = pd.read_csv(baseline / "reference_bars.csv")
    raw.index = pd.DatetimeIndex(pd.to_datetime(raw.pop("bar_open_utc"), utc=True))
    frame = reference_bars(raw)
    config = yaml.safe_load(Path("config/settings.yaml").read_text())
    sig = directions(frame, config)
    start, end = pd.Timestamp("2026-03-28", tz="UTC"), pd.Timestamp("2026-09-28", tz="UTC")
    t, b, a = [
        np.load(baseline / "tape" / f"{key}.npy", mmap_mode="r") for key in ("time", "bid", "ask")
    ]
    left, right = np.searchsorted(t, [start.value // 10**6, end.value // 10**6])
    t, b, a = t[left:right], b[left:right], a[left:right]
    engine = Replay(t, b, a, broker, cost_scenario=cost_scenario)
    recovery_signal = sig["LEGACY_MSS"] if recovery_rule == "MSS" else sig["B1"]
    prev = 0
    count = 0
    for i in np.flatnonzero((sig["B1"].to_numpy() != 0) | (recovery_signal.to_numpy() != 0)):
        when = frame.index[i] + pd.Timedelta(minutes=15)
        if not start <= when < end:
            continue
        stamp = when.value // 10**6
        j = int(np.searchsorted(t, stamp))
        if j >= len(t) or t[j] - stamp >= 900000:
            engine.rejections["tick_gap"] += 1
            continue
        engine.advance(prev, j + 1)
        prev = j + 1
        engine.on_signal(
            j, int(sig["B1"].iloc[i]), int(recovery_signal.iloc[i]), float(frame.atr.iloc[i])
        )
        count += 1
    engine.advance(prev, len(t))
    if engine.legs:
        engine._close_basket(len(t) - 1, "END_OF_SAMPLE")
    legs, baskets = pd.DataFrame(engine.leg_rows), pd.DataFrame(engine.basket_rows)
    suffix = f"{recovery_rule}_{'archival_cost' if cost_scenario else 'spread_only'}"
    legs.to_csv(output / f"legs_{suffix}.csv", index=False)
    baskets.to_csv(output / f"baskets_{suffix}.csv", index=False)
    if len(legs):
        np.testing.assert_allclose(200.0 + legs.net.sum(), engine.balance, atol=1e-6)
    if len(baskets):
        np.testing.assert_allclose(200.0 + baskets.net.cumsum(), baskets.balance, atol=1e-6)
    losses = -baskets.loc[baskets.net < 0, "net"].sum() if len(baskets) else 0
    result = {
        "recovery_rule": recovery_rule,
        "cost_scenario": cost_scenario,
        "initial_balance": 200.0,
        "final_balance": engine.balance,
        "return_pct": (engine.balance / 200.0 - 1) * 100,
        "basket_count": len(baskets),
        "leg_count": len(legs),
        "recovery_count": engine.recovery_count,
        "signal_events": count,
        "win_rate": float((baskets.net > 0).mean()) if len(baskets) else None,
        "profit_factor": float(baskets.loc[baskets.net > 0, "net"].sum() / losses)
        if losses
        else None,
        "max_tick_equity_dd_pct": engine.max_dd * 100,
        "hwm_halted": engine.halted,
        "close_reasons": engine.close_reasons,
        "rejections": engine.rejections,
    }
    print(json.dumps(result), flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    contract = {
        "start_utc": "2026-03-28T00:00:00+00:00",
        "end_exclusive_utc": "2026-09-28T00:00:00+00:00",
        "source": str(args.baseline),
        "capture": str(args.capture),
        "capture_manifest_sha256": hashlib.sha256(
            (args.capture / "manifest.json").read_bytes()
        ).hexdigest(),
        "capital_usd": 200.0,
        "entry_signal": "B1_TP25 completed M15",
        "entry_fill": "first actual tick after signal, Ask BUY / Bid SELL",
        "recovery_rules": ["MSS", "B1"],
        "recovery_fill": "first actual tick after trigger",
        "lots": [0.01, 0.02],
        "basket_budget": "min(15% entry equity, USD30)",
        "basket_tp": "net strictly positive after recovery; single leg uses 2.5R",
        "daily": "15% day-start equity halt new baskets; maximum two new baskets",
        "hwm": "20% floating equity drawdown permanent halt and close",
        "margin": "notional divided by 1:1000 proxy; broker order approval unverified",
        "costs": ["actual Bid/Ask spread only", "current-spec swap UTC + hypothetical 0.10R fee"],
        "limitations": [
            "Research reconstruction; no runtime BasketManager parity",
            "Market entry assumption differs from current PLACE_LIMIT intent",
            "MSS is legacy M15 detector approximation, not native M5 SMC",
            "Commission, slippage, margin and stop-out histories unavailable",
            "No broker order execution or notifier",
        ],
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "settings_sha256": hashlib.sha256(Path("config/settings.yaml").read_bytes()).hexdigest(),
        "baseline_manifest_sha256": hashlib.sha256(
            (args.baseline / "manifest.json").read_bytes()
        ).hexdigest(),
    }
    (args.output / "contract.json").write_text(json.dumps(contract, indent=2))
    results = [
        run(args.baseline, args.capture, args.output, rule, scenario)
        for rule in ("MSS", "B1")
        for scenario in (False, True)
    ]
    (args.output / "results.json").write_text(json.dumps(results, indent=2))
    (args.output / "COMPLETE").write_text("Offline historical reconstruction only.\n")


if __name__ == "__main__":
    main()
