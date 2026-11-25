"""Offline comparison of the selected 26b8 detector with four entry-only variants."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.c22_selected.strategy import CANDIDATE_ID, CONFIG_PATH, CONTRACT, _rules_id, verify_sources
from scripts.research.breakout_models import Costs
from scripts.research.breakout_replay import replay
from scripts.research.c22_frequency_data import load_bars, verify_input
from scripts.research.reward156_search import prepare_candidate
from scripts.research.reward156_tuning import closed_h4_ema
from scripts.research.rollover import SwapPolicy


def entry_profiles(bars):
    """Use completed UTC bid M15s. Columns are decisions at bar end."""
    native, rules = prepare_candidate(bars, CONTRACT)
    if _rules_id(rules) != CANDIDATE_ID:
        raise ValueError("selected native rules mismatch")
    groups = bars.resample("4h", origin="start_day")
    full = groups.close.count().eq(16)
    h4 = groups.agg({"high": "max", "low": "min", "close": "last"}).loc[full]
    up, down = h4.high.diff(), -h4.low.diff()
    true_range = pd.concat([h4.high - h4.low, (h4.high - h4.close.shift()).abs(),
                            (h4.low - h4.close.shift()).abs()], axis=1).max(axis=1)

    def wilder(values):
        return values.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()

    atr4 = wilder(true_range)
    plus = wilder(up.where((up > down) & (up > 0), 0.0)) / atr4
    minus = wilder(down.where((down > up) & (down > 0), 0.0)) / atr4
    adx = wilder(100 * (plus - minus).abs() / (plus + minus).replace(0, np.nan))
    decision = bars.index + pd.Timedelta(minutes=15)
    prior = decision.floor("4h") - pd.Timedelta(hours=4)
    strength = pd.Series(adx.reindex(prior).to_numpy(), index=bars.index)
    ready = full.cumsum().reindex(prior, fill_value=0).to_numpy() >= 201
    native["direction"] = native.direction.where(ready, 0)
    signals = pd.DataFrame({"native": native.direction}, index=bars.index)

    macro = closed_h4_ema(bars, CONTRACT["macro_span"])
    price, atr = native.close, native.atr
    ema20 = price.ewm(span=20, adjust=False, min_periods=20).mean()
    ema50 = price.ewm(span=50, adjust=False, min_periods=50).mean()
    highs, lows = native.high.shift(), native.low.shift()
    sell_ok = ((lows.rolling(48).min() - price <= atr) & (ema20 - price <= 1.5 * atr)
               & (ema50 - price <= 1.5 * atr))
    buy_ok = ((price - highs.rolling(48).max() <= atr) & (price - ema20 <= 1.5 * atr)
              & (price - ema50 <= 1.5 * atr))
    extra_sell = ((price < lows.rolling(32).min()) & (price < ema50)
                  & (ema50 < ema50.shift(4)) & (price < macro))
    extra_buy = ((price > highs.rolling(32).max()) & (price > ema50)
                 & (ema50 > ema50.shift(4)) & (price > macro))
    for floor in (20, 25):
        enabled = ready & strength.ge(floor)
        retained = native.direction.where(enabled & ((native.direction.eq(-1) & sell_ok)
                                                      | (native.direction.eq(1) & buy_ok)), 0)
        signals[f"filter{floor}"] = retained
        # The macro gate makes simultaneous opposite directions impossible.
        signals[f"add32_adx{floor}"] = np.select(
            [enabled & sell_ok & extra_sell, enabled & buy_ok & extra_buy], [-1, 1], default=retained
        )
    return native, signals, rules


def tick_comparison(folder, protocol, start, end, warmup=None):
    """Separate $200 books using observed bid/ask, mandatory swap, and native admission."""
    verify_sources(json.loads(CONFIG_PATH.read_text()))
    manifest = verify_input(folder)
    required = {"bars.csv", "tape/time.npy", "tape/bid.npy", "tape/ask.npy"}
    if not required.issubset(manifest["artifacts"]):
        raise ValueError("missing bar/tick hashes in the research manifest")
    bars = load_bars(folder / "bars.csv")
    if warmup is not None:
        path = warmup / "bars.csv"
        expected = json.loads((warmup / "manifest.json").read_text())["artifacts"]["bars.csv"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("warmup bar hash mismatch")
        history = load_bars(path)
        bars = pd.concat([history.loc[history.index < bars.index[0]], bars])
    native, signals, rules = entry_profiles(bars)
    broker = protocol["broker"]
    swap = SwapPolicy.from_broker(broker)
    ticks = [np.load(folder / "tape" / f"{key}.npy", mmap_mode="r") for key in ("time", "bid", "ask")]
    if start < pd.Timestamp(ticks[0][0], unit="ms", tz="UTC").floor("D") or (
        end > pd.Timestamp(ticks[0][-1], unit="ms", tz="UTC").ceil("D")
    ):
        raise ValueError("requested window extends outside the supplied tick archive")
    result = []
    for view in ("base", "stress"):
        costs = Costs(**protocol["views"][view])
        for name, direction in signals.items():
            book = replay(native.assign(direction=direction), ticks, broker, rules, costs,
                          start=start, end=end, swap_policy=swap)
            if any(t["volume"] != .01 or t["risk_pct"] > 10 + 1e-8 for t in book["ledger"]):
                raise ValueError("fixed-lot/risk invariant failed")
            result.append(dict(profile=name, view=view, net=book["net_usd"], pf=book["profit_factor"],
                               dd_pct=book["max_dd_pct"], win=book["win_rate"], n=book["trades"],
                               swap=book["swap_usd"], ledger=book["ledger"]))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="verified bars.csv and tape/ manifest folder")
    parser.add_argument("--protocol", required=True, type=Path, help="research JSON with broker and base/stress costs")
    parser.add_argument("--warmup", type=Path, help="earlier verified bars for indicator warmup")
    parser.add_argument("--start", required=True, help="inclusive UTC date")
    parser.add_argument("--end", required=True, help="exclusive UTC date")
    parser.add_argument("--output", required=True, type=Path, help="new results JSON")
    args = parser.parse_args()
    result = tick_comparison(args.input, json.loads(args.protocol.read_text()),
                             pd.Timestamp(args.start, tz="UTC"), pd.Timestamp(args.end, tz="UTC"), args.warmup)
    with args.output.open("x") as dest:
        json.dump(result, dest, allow_nan=False)


if __name__ == "__main__":
    main()
