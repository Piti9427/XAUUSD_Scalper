"""Deterministic counterexamples for the 2026-09-12 Master Pro review.

These are small Python transcriptions of cited Pine branches, NOT a Pine
interpreter, compiler, backtest, or proof of live TradingView behavior.
Run: python3 scripts/debug/reviews/reproduce_master_pro_v6_review.py
"""

from math import sqrt


def long_exit(entry, sl, tp1, tp2, high, low):
    """Pine lines 460-478, initially active LONG without relocated BE."""
    be = high >= tp1
    if be:
        sl = entry + 0.10
    if high >= tp2:
        return "TP2"
    if low <= sl:
        return "BE" if be else "SL"
    return "ACTIVE"


def main():
    # A valid TSS buy at CLOSE: prior low=98.5, pierce=0.5, close=100.
    # All high/low movement occurred before activation at close (lines 348-358).
    result = long_exit(100, 97.7, 102.3, 105.75, high=111, low=98)
    assert result == "TP2"
    print("REPRODUCED: close-entry uses pre-entry high -> TP2; expected still open")

    # Existing long, known path 100 -> 98 -> 103 -> 100: SL first.
    result = long_exit(100, 99, 101, 102.5, high=103, low=98)
    assert result == "TP2"
    print("REPRODUCED: SL-first path -> TP2; expected SL")

    # Known path 100 -> 99.5 -> 101.2 -> 101.1: low before BE activation.
    result = long_exit(100, 99, 101, 102.5, high=101.2, low=99.5)
    assert result == "BE"
    print("REPRODUCED: pre-TP1 low reused against new BE -> closed; expected runner")

    # Pending buy @100, SL99; path 101 -> 106 -> 98 -> 101.
    # High106 occurs BEFORE fill; after fill, path crosses stop99.
    filled = 98 <= 100  # Pine 437
    result = long_exit(100, 99, 101, 102.5, high=106, low=98)
    assert filled and result == "TP2"
    print("REPRODUCED: pending fill inherits pre-fill high -> TP2; expected SL")

    # Pine 80-81 and 180-181 include current sample in rolling extrema.
    dxy_highs = [100] * 9 + [110]
    dxy_lows = [100] * 9 + [90]
    assert dxy_highs[-1] > max(dxy_highs[:-1])
    assert dxy_lows[-1] < min(dxy_lows[:-1])
    assert dxy_highs[-1] <= max(dxy_highs)
    assert dxy_lows[-1] >= min(dxy_lows)
    print("REPRODUCED: fresh DXY high/low both pass claimed non-confirmation checks")

    # Reduced Pine 165-225, 322-325. AsianLow105, confirmed swingHigh109;
    # bullish H1 and session gates held true, other pools do not interfere.
    bars = [
        (106, 108, 100, 106),
        (106, 111, 106, 110),
        (105, 106, 104, 105),
        (111, 112, 105.5, 106),
        (112, 113, 110, 111),
    ]
    sweep_bar = mss_bar = None
    extremum = None
    for i, (o, h, low, c) in enumerate(bars):
        sweep = low < 105 and c >= 105 and 0.30 <= 105 - low <= 8
        if sweep:
            sweep_bar, extremum = i, low
        elif sweep_bar is not None and i - sweep_bar <= 8:
            extremum = min(extremum, low)
        if (
            sweep_bar is not None
            and 0 < i - sweep_bar <= 8
            and c > 109
            and c > o
            and abs(c - o) / (h - low) >= 0.45
        ):
            mss_bar = i
    assert (sweep_bar, mss_bar, extremum) == (2, 1, 104)
    ce = (bars[4][2] + bars[2][1]) / 2
    sl = extremum - 0.30
    assert bars[4][2] - bars[2][1] >= 0.30 and 4 - mss_bar <= 4
    assert 0 < ce - sl <= 25
    print(f"REPRODUCED: old MSS + new sweep -> entry {ce:.2f}, SL {sl:.2f}; original SL99.70")

    # Pine time is opening timestamp; standard M15 bars never open at 20:55.
    openings = [20 * 60 + 30, 20 * 60 + 45, 21 * 60]
    first_flat = next(t for t in openings if 20 * 60 + 55 <= t < 23 * 60)
    assert first_flat == 21 * 60
    print("REPRODUCED: M15 rollover first eligible bar opens21:00; deadline20:55")

    n, wins, z = 4, 3, 1.959963984540054
    p = wins / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    print(f"Wilson95% for documented3/4 (IID assumption): {center - half:.2%}..{center + half:.2%}")
    print(f"Gross full-target payoff with50% at1R,50% at2.5R: {0.5 * 1 + 0.5 * 2.5:.2f}R")
    print("7 counterexamples reproduced. No Pine compiler/live broker invoked.")


if __name__ == "__main__":
    main()
