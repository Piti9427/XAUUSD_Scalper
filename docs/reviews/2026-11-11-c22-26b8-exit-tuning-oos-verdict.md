# Selected26b8 TP/exit tuning — OOS verdict (2026-11-11)

**Verdict: no exit change. Native 26b8 SELL TP1.35R / BUY TP3R / BE1R stays.
Both locked exit candidates FAIL the predeclared no-regression gates on
2023-01..2024-08, a window not used for exit selection.** No config, VM or runtime change.
Sealed 2020–22 holdout NOT opened (not needed: nothing passed).

Owner question: can the take-profit side be widened/tuned for more profit than the current R:R?

## Prior evidence reused (not re-run)

- `runs/c22-26b8-exit-tuning-2026-11-01`: 30 exit variants on 2024-09..2026-10
  (SELL TP 2/2.5/3R, BUY TP 2/2.5/4R, BE 1.25–2R, lock, ATR/swing trailing, no-TP runner,
  time exits, combos). Walk-forward pick (best train net/DD, 7 folds) **lost to native in all
  4 views** (e.g. fee_x040 $200: 705 vs 782). Only fixed variant beating native in all 4
  fixed-OOS views: `sell_tp2`. Trailing 3ATR beat native in fee_x040 $200 (trail3atr 896,
  sell_notp_trail3atr 859 vs 782) but not all 4 views; tighter trails were worst (trail2atr 636,
  trail1.5atr 513). SELL BE 1.25/1.5/2R all 937.31 (trigger ≥ near TP → BE inert); BUY TP2R 602.
- `runs/c22-26b8-fail-rootcause-2026-11-02`: at $200 the result is dominated by 10% cap
  path-dependence (81–100% of every delta). Longer SELL TP turns 1.35R winners into BE
  scratches, balance stalls, cap rejects more trades. Survivor `S1` = SELL TP3R only if
  risk ≤7% of balance (tested there on top of an Asia BUY block, an entry change).
- `runs/c22-26b8-candidate-backtest-2026-11-02` "holdout2026" slice lies inside the selection
  window, so it is not a holdout; it already showed S1 worse than base at $200.

## This run

Protocol frozen before data contact: [protocol.json](../../runs/c22-26b8-exit-oos-2026-11-11/protocol.json)
(sha256 `a7e0d40b…7f53`), runner `run.py`, output `result.json`.

- Baseline: native 26b8 (no Asia block). Candidates: C1 = SELL TP2R; C2 = SELL TP3R if risk ≤7% balance.
- Window 2023-01-01..2024-09-01, reused manifest-hashed tape from the two-slot holdout.
- Swap-inclusive views: base+swap, stress+swap (gating), fee+swap (reported). Current broker swap
  applied to 2023-24 → COST_INCONCLUSIVE.
- Balances: $313 (estimated live equity after the 2026-11-01 −$1,612.81 non-trade deal and the
  2026-11-10 TPs) and $200.
- Gate per required cell (base/stress × 313/200): net, max DD, min equity, profitable months all ≥ native.
- Parity precheck PASS: native reproduced two-slot native control exactly (−175.73 / −177.82 / −173.86),
  second engine identical.

| View | Native net / DD / minEq | C1 SELL TP2R | C2 TP3R if risk≤7% |
| --- | --- | --- | --- |
| base $313 | −262.83 / 89.90% / 36.81 | −286.82 / 92.72% / 26.18 | −265.53 / 91.31% / 30.92 |
| stress $313 | −285.40 / 92.49% / 27.60 | −287.17 / 92.97% / 25.83 | −287.40 / 93.03% / 25.60 |
| base $200 | −175.73 / 90.34% / 24.27 | −177.35 / 90.81% / 22.65 | −176.74 / 90.42% / 23.26 |
| stress $200 | −177.82 / 91.29% / 22.18 | −179.10 / 91.79% / 20.90 | −177.29 / 91.07% / 22.71 (pass) |
| fee $313 (info) | −287.64 / 93.09% | −288.06 / 93.21% | −288.75 / 93.39% |

C1 fails net/DD/minEq in all 4 required cells. C2 fails 3 of 4. Mechanism matches the root-cause
report: SELL win rate falls 36–40% → 14–25%, TP exits fall (base $313: 58 → 34 / 29), cap
rejections rise (185 → 209 / 197).

## Interpretation

- Supportable claim: no exit variant showed robust improvement across 2024-26 walk-forward plus
  2023-24 OOS. This does not prove 1.35R optimal; several 2023-24 deltas are small ($1–5 at $200,
  −2.7 C2 base $313; only C1 base $313 −24 is a clear gap), and FAIL rests on the strict ≥ rule.
  Wider SELL targets win only in strong trend
  segments (TP3R at $1000: +291.7 of +356.8 came from the single 2026-03..06 fold) and lose in range regimes.
- The big loss in 2023-24 belongs to native 26b8 itself (about −84% to −92% in every view, BUY win ≈14%).
  It comes from entries and regime, not exits. Exit tuning cannot fix it; earlier regime filters
  were also NO_IMPROVEMENT.
- Cap sensitivity: live SELL risks were $17.86/$21.10/$24.36, under the $31 cap at $313; it binds
  there only in high ATR or after drawdown (2023-24 rejections followed balance collapse). At $200
  ($20 cap) it binds far more. Any exit that slows balance growth then reduces admitted trades.

## Not done / limits

- Historical swap unknown; Exness tick replay ≠ MT5 broker fills; 3 live trades are not evidence.
- No new variants were tried on 2023-24 (no retune). Sealed 2020–22 holdout untouched.
