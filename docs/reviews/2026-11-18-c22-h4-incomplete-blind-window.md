# C22: the daily H4-incomplete blind window (2026-11-18)

## Owner observation
From 17 Nov late evening to 18 Nov morning, gold fell about 70 points (roughly 3850 to 3770), but the bot sold only at the bottom: 3778.10, at 06:30 UTC on 18 Nov.

## Verified cause (read-only journal, 2026-11-17 13:30 to 2026-11-18 06:35 UTC)
| UTC | Bot state |
|---|---|
| 14:30–21:49 | WAIT `no_signal` on every bar (no breakout yet) |
| 21:49 | `OperationalError`, the backup lock. Fix A was deployed 18 Nov 01:28 |
| 21:58–23:00 | `quote_stale` (daily break) |
| 23:00–23:14 | `armed_trial_new_closed_m15_required` |
| **00:00–03:59 on 18 Nov** | **BLOCKED `macro_latest_h4_incomplete`**. The steep part of the drop happened here |
| 01:18–01:29 | Deploy of 70b1 and then 6d7b (source_drift restart) |
| 04:00–06:29 | WAIT `no_signal` |
| 06:30 | SELL filled at 3778.102 |

## Mechanism
- The 20:00–24:00 UTC H4 bar contains the daily break, so it never has 16 M15 bars.
- The macro rule requires the latest H4 to be complete. It is checked in `scripts/c22_selected/strategy.py:134` (live) and `scripts/research/c22_frequency_adapter.py:118–131` (research).
- So every day from 00:00 to about 04:00 UTC (07:00–11:00 ICT), the macro EMA is unavailable and every signal fails closed.
- The backtest has the same rule. Every historical number already excludes this window, so it is not a live-only bug.

## Size in history (raw signal bars blocked by h4_incomplete)
| Segment | Blocked | SELL / BUY |
|---|---:|---:|
| 2020 | 117 | 47 / 70 |
| 2021 | 143 | 67 / 76 |
| 2022 | 150 | 81 / 69 |
| 2023 | 142 | 82 / 60 |
| 2024a | 95 | 32 / 63 |
| 2024b25 | 181 | 92 / 89 |
| 2026 | 127 | 90 / 37 |

- That is about 14% of all raw signal bars, almost all of them between 23:00 and 03:59 UTC.
- These are signal *bars*, not trades. Their profitability is unknown, and nothing here says that opening the window would help.

## Possible research (not started; needs owner go-ahead and a frozen protocol)
- **One mechanism only:** when the latest H4 is incomplete because of the scheduled daily break, use the last complete H4 EMA instead of failing closed.
- **Method:** LOYO against native 26b8 in both views, under the no-regression rule, then the forward shadow.
- **Caveat:** older research found Asia BUY entries poor (win 9.7%). The result may be SELL-only or negative.

## Research result: frozen LOYO, **FAIL → keep native** (2026-11-18)
- **Location:** `runs/c22-h4-fill-2026-11-18/` (`h4fill.py`, `protocol.json` sha256 `23bb4023…f801`, `cells.json`, `verdict.json`).
- **Setup:** 7 yearly books at $313, base and stress. Specs native, fill_both and fill_sell.
- **Parity:** PARITY_OK. The overlay changes only h4_incomplete rows. The split warm-up equals unsplit native.
- **Picks:** native in all 7 folds. Neither fill spec passes the training gate in any fold.

| Year | Native base | fill_both base | fill_sell base |
|---|---:|---:|---:|
| 2020 | −182.65 | −236.55 | −227.93 |
| 2021 | −213.36 | −251.33 | −237.54 |
| 2022 | −23.59 | −8.62 | −61.41 |
| 2023 | −102.71 | −90.11 | −100.94 |
| 2024a | −173.88 | −221.48 | −187.89 |
| 2024b25 | +906.07 | +832.91 | +953.29 |
| **2026** | **+887.35** (DD 43.0) | **+399.51** (DD 74.0) | **+573.22** (DD 53.0) |

### Attribution (base)
- **The added entries are poor quality in their own right.** Most of them fall at 00:00–04:00 UTC.
  - fill_both: the added trades lose in 6 of 7 years. Win rates are 10–35%. In 2026, 49 added trades total −157.
  - fill_sell: the added trades lose in 6 of 7 years. In 2026, 35 added trades total −180.4, with a 34% win rate.
- **They also displace native winners.** In 2026, fill_sell displaces 16 native trades worth +133.7, and fill_both displaces 27 worth +330.7.
- **Conclusion:** the blind window acts as a quality filter.
  - Breakouts just after the daily break, in thin Asia liquidity, fail far more often than they succeed.
  - The 18 Nov drop was a winner the window happened to miss. Systematically, entries in that window lose.
- **No derived iteration:** the added trades lose on their own, not only through displacement, so there is no mechanism left to repair. Keep native unchanged.
