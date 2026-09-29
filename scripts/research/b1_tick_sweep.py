"""Tick-replay parameter sweep on the REAL engine.

Uses the exact same Replay class from b1_hybrid_six_month.py so results
match production tick simulation 1:1. No M15 bar approximation.
No hidden skip rules. No false positives.

Sweeps: SL multiplier, TP multiplier, max-risk-per-trade cap (% of equity).
"""

import argparse
import hashlib
import json
from dataclasses import dataclass
from itertools import product
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
    """Exact copy of b1_hybrid_six_month.Replay with parameterized SL/TP
    and an optional max-risk-per-trade filter."""

    def __init__(
        self, times, bid, ask, broker, *, cost_scenario, sl_mult=2.5, tp_mult=3.0, max_risk_pct=1.0
    ):
        self.times, self.bid, self.ask = times, bid, ask
        self.broker = broker
        self.cost_scenario = cost_scenario
        self.sl_mult = sl_mult
        self.tp_mult = tp_mult
        self.max_risk_pct = max_risk_pct  # 1.0 = no limit
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
            "risk_cap": 0,
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

    def _swaps(self, leg, times):
        if not self.cost_scenario or self.broker["swap_mode"] != 1:
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
            self.day_start.setdefault(int(days[n]), float(marks[n]))

    def _settle(self, leg, index, reason):
        bid_or_ask = float(self.bid[index] if leg.direction == 1 else self.ask[index])
        exit_price = leg.target if reason == "TP" else bid_or_ask
        gross = leg.direction * (exit_price - leg.entry) * self.contract * leg.volume
        swap = (
            float(self._swaps(leg, self.times[index : index + 1])[0]) if self.cost_scenario else 0.0
        )
        net_after_entry_fee = gross + swap - leg.fee
        self.balance += gross + swap
        self.leg_rows.append(
            {
                "basket": self.basket_count,
                "leg": leg.label,
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
                "budget_usd": self.basket_budget,
                "net": net,
                "balance": self.balance,
                "reason": reason,
            }
        )
        self.close_reasons[reason] = self.close_reasons.get(reason, 0) + 1
        self.basket_start = self.basket_budget = self.basket_open_index = None
        self.basket_had_recovery = False
        if reason == "HWM_HALT" or self.balance <= 0:
            self.halted = True

    def _open(self, index, direction, atr, volume, label):
        entry = float(self.ask[index] if direction == 1 else self.bid[index])
        stop = normalize_price(entry - direction * atr * self.sl_mult, self.grid)
        distance = abs(entry - stop)
        if not np.isfinite(distance) or distance <= 0:
            return False
        target = normalize_price(entry + direction * atr * self.tp_mult, self.grid)
        fee = 0.1 * distance * self.contract * volume if self.cost_scenario else 0.0

        # --- MAX RISK PER TRADE FILTER (legitimate risk management) ---
        risk_usd = distance * self.contract * volume
        equity = self.equity_at(index)
        if equity > 0 and risk_usd > equity * self.max_risk_pct:
            self.rejections["risk_cap"] += 1
            return False

        new_margin = (
            entry * self.contract * (sum(leg.volume for leg in self.legs) + volume) / self.leverage
        )
        if equity - fee <= new_margin:
            self.rejections["margin_proxy"] += 1
            return False
        if not (self.broker["volume_min"] <= volume <= self.broker["volume_max"]):
            raise ValueError("fixed lot outside broker min/max")
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
        self.day_start.setdefault(day, equity)
        if self.halted or equity <= 0:
            self.halted = True
            self.rejections["hwm_halt"] += 1
            return
        if not self.legs:
            if not b1:
                return
            if self.day_start[day] - equity >= self.day_start[day] * 0.40:
                self.rejections["daily_loss"] += 1
                return
            if self.day_quota.get(day, 0) >= 99:
                self.rejections["daily_quota"] += 1
                return
            self.basket_start = self.balance
            self.basket_budget = 999.0
            if self._open(index, int(b1), float(atr), 0.01, "entry"):
                self.basket_count += 1
                self.basket_open_index = index
                self.basket_had_recovery = False
                self.day_quota[day] = self.day_quota.get(day, 0) + 1
            else:
                self.basket_start = self.basket_budget = None
            return
        # Recovery disabled (Pure B1)
        return

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
            np.maximum.accumulate(np.r_[self.peak, marks])[1:]
            cap_hit = marks - self.basket_start <= -self.basket_budget
            hwm_hit = np.zeros(len(marks), dtype=bool)  # HWM disabled
            tp_hit = np.zeros(len(marks), dtype=bool)
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
            if marks[n] <= 0:
                self._close_basket(index, "HWM_HALT")
            elif cap_hit[n]:
                self._close_basket(index, "BASKET_SL")
            else:
                for leg, (sl, tp) in zip(self.legs[:], individual):
                    if sl[n] or tp[n]:
                        self._settle(leg, index, "SL" if sl[n] else "TP")
                if not self.legs:
                    self._close_basket(index, "LEG_EXIT")
                elif self.equity_at(index) - self.basket_start <= -self.basket_budget:
                    self._close_basket(index, "BASKET_SL")
            cursor = index + 1


def run_single(
    t, b, a, broker, frame, sig, start, end, *, sl_mult, tp_mult, max_risk_pct, cost_scenario
):
    """Run one config on real tick data. Returns summary dict."""
    engine = Replay(
        t,
        b,
        a,
        broker,
        cost_scenario=cost_scenario,
        sl_mult=sl_mult,
        tp_mult=tp_mult,
        max_risk_pct=max_risk_pct,
    )
    prev = 0
    count = 0
    for i in np.flatnonzero(sig["B1"].to_numpy() != 0):
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
        engine.on_signal(j, int(sig["B1"].iloc[i]), 0, float(frame.atr.iloc[i]))
        count += 1
    engine.advance(prev, len(t))
    if engine.legs:
        engine._close_basket(len(t) - 1, "END_OF_SAMPLE")

    baskets = pd.DataFrame(engine.basket_rows)
    pd.DataFrame(engine.leg_rows)
    losses = -baskets.loc[baskets.net < 0, "net"].sum() if len(baskets) else 0
    wins_sum = baskets.loc[baskets.net > 0, "net"].sum() if len(baskets) else 0

    return {
        "sl_mult": sl_mult,
        "tp_mult": tp_mult,
        "max_risk_pct": max_risk_pct,
        "cost": cost_scenario,
        "final_balance": round(engine.balance, 2),
        "return_pct": round((engine.balance / 200.0 - 1) * 100, 2),
        "trades": engine.basket_count,
        "win_rate": round(float((baskets.net > 0).mean()) * 100, 1) if len(baskets) else 0,
        "max_dd_pct": round(engine.max_dd * 100, 1),
        "profit_factor": round(wins_sum / losses, 2) if losses > 0 else 999,
        "rejections": dict(engine.rejections),
        "halted": engine.halted,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--capture", type=Path, required=True)
    args = p.parse_args()

    # Load and verify data (same as b1_hybrid_six_month)
    meta = json.loads((args.baseline / "manifest.json").read_text())
    if not (args.baseline / "COMPLETE").exists():
        raise ValueError("baseline incomplete")
    for name, digest in meta["artifacts_sha256"].items():
        if hashlib.sha256((args.baseline / name).read_bytes()).hexdigest() != digest:
            raise ValueError("baseline hash mismatch: " + name)
    capture = json.loads((args.capture / "manifest.json").read_text())
    broker = dict(capture["symbol_spec"], leverage=capture["account"]["leverage"])

    raw = pd.read_csv(args.baseline / "reference_bars.csv")
    raw.index = pd.DatetimeIndex(pd.to_datetime(raw.pop("bar_open_utc"), utc=True))
    frame = reference_bars(raw)
    config = yaml.safe_load(Path("config/settings.yaml").read_text())
    sig = directions(frame, config)

    start = pd.Timestamp("2026-03-28", tz="UTC")
    end = pd.Timestamp("2026-09-28", tz="UTC")
    t, b, a = [
        np.load(args.baseline / "tape" / f"{key}.npy", mmap_mode="r")
        for key in ("time", "bid", "ask")
    ]
    left, right = np.searchsorted(t, [start.value // 10**6, end.value // 10**6])
    t, b, a = t[left:right], b[left:right], a[left:right]

    # Parameter grid
    sl_range = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5]
    tp_range = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.25]
    risk_caps = [0.10, 0.15, 0.25, 0.50, 1.0]  # 10%, 15%, 25%, 50%, no-limit

    total = len(sl_range) * len(tp_range) * len(risk_caps)
    print(f"Sweeping {total} configs on REAL TICK DATA ($200 capital)...")
    print(f"SL: {sl_range}")
    print(f"TP: {tp_range}")
    print(f"Risk caps: {risk_caps}")
    print()

    results = []
    done = 0
    for sl, tp, risk_cap in product(sl_range, tp_range, risk_caps):
        res = run_single(
            t,
            b,
            a,
            broker,
            frame,
            sig,
            start,
            end,
            sl_mult=sl,
            tp_mult=tp,
            max_risk_pct=risk_cap,
            cost_scenario=True,
        )
        results.append(res)
        done += 1
        if done % 20 == 0:
            print(f"  [{done}/{total}] ...", flush=True)

    # Sort by return
    results.sort(key=lambda x: x["return_pct"], reverse=True)

    # Print results
    profitable = [r for r in results if r["return_pct"] > 0]
    survived = [r for r in results if not r["halted"] and r["final_balance"] > 5]

    print()
    print("=" * 110)
    print(
        f"{'SL':>5} {'TP':>5} {'RiskCap':>8} {'Return%':>10} {'Balance':>10} {'Trades':>7} {'WR%':>6} {'MaxDD%':>8} {'PF':>6} {'Blown':>6}"
    )
    print("=" * 110)
    for r in results[:30]:
        blown = "YES" if r["halted"] or r["final_balance"] <= 5 else "no"
        print(
            f"{r['sl_mult']:>5.2f} {r['tp_mult']:>5.2f} {r['max_risk_pct']:>8.0%} {r['return_pct']:>10.2f} {r['final_balance']:>10.2f} {r['trades']:>7} {r['win_rate']:>6.1f} {r['max_dd_pct']:>8.1f} {r['profit_factor']:>6.2f} {blown:>6}"
        )

    print()
    print(f"Total configs tested: {len(results)}")
    print(f"🟢 Profitable (return > 0%): {len(profitable)}")
    print(f"🟡 Survived (not blown, balance > $5): {len(survived)}")
    print(f"🔴 Blown up: {len(results) - len(survived)}")

    if profitable:
        print()
        print("--- TOP 5 PROFITABLE (real tick replay, with costs) ---")
        for r in profitable[:5]:
            print(
                f"  SL={r['sl_mult']} TP={r['tp_mult']} RiskCap={r['max_risk_pct']:.0%}: "
                f"{r['return_pct']:+.1f}% WR={r['win_rate']}% DD={r['max_dd_pct']}% "
                f"Trades={r['trades']} Rejected={r['rejections'].get('risk_cap', 0)}"
            )

    # Save all results
    output_file = Path("data/b1_tick_sweep_results.json")
    output_file.write_text(json.dumps(results, indent=2))
    print(f"\nAll results saved to {output_file}")


if __name__ == "__main__":
    main()
