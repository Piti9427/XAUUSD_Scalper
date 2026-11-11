# Selected26b8 BUY entry / bigger BUY TP — verdict (2026-11-11)

**Verdict: bigger BUY TP does not help. All 12 conditional BUY-TP variants FAIL. Only the
previously locked Asia BUY block (no BUY 04:00–06:59 UTC = 11:00–13:59 Bangkok) passes
fold-OOS no-regression (4/4 cells) and the 2023-24 stress check (4/4 cells).** No config/VM change.

Owner ask: tune BUY side for more profit, e.g. place a bigger TP.
Protocol frozen before the run: [protocol.json](../../runs/c22-26b8-buy-entry-2026-11-11/protocol.json)
(sha256 `7cf7bd20…bd33`); `run.py`, `result.json`, `probe.json` in the same folder.

## Already covered, not repeated
Static BUY TP 1.35–3R/SL/BE (matrix-tuning 10-25), BUY TP 2/2.5/4R and BE (exit-tuning 11-01;
TP4R worst), entry filters ADX/ER/chop/EMA-slope/ATR/hour/spread + ML (regime-filter 11-01:
NO_IMPROVEMENT), RSI 7/14/21 × 25/30/35 (Oct).

## Probe: BUY contribution (native, swap-inclusive)
- Discovery 2024-09..2026-10: BUY ≈ +$896 (base $200). BUY-off cuts net 1945 → 668 and raises DD 34 → 49%. BUY is needed.
- 2023-24: BUY −$160..−$232, win ≈12–14%. BUY-off is better there but still −$124..−$201, so no BUY change makes that window profitable.

## New test: conditional BUY TP
BUY TP 4R/5R only when a causal strength feature ≥ p50/p75 at the signal (closed-H4 EMA200
distance/ATR, EMA50 16-bar slope/ATR, ATR vs 30-day median), or TP 2R when weak. Levels come
from the BUY-signal feature distribution only (no outcomes). SELL untouched. Parity: native
1945.33 and asia 1879.21 (base $200) reproduce the probe.

Gate: 7 fresh-account OOS folds, sums vs native, all of net/maxDD/minEq/profitable months ≥ native,
in base+swap and stress+swap at $313 and $200.

| Fold-OOS sum (base $313 / stress $313) | net | DD | BUY win (full) |
| --- | --- | --- | --- |
| native | 1476 / 1290 | 58.3 / 62.5 | 25.2% |
| asia_block | **1556 / 1318** | **50.0 / 54.4** | 27.5% |
| wide4 ATR≥p50 (best wide) | 1578 / 1133 | 54.6 / 58.8 | 23.2% |
| wide4 slope≥p50 | 1383 / 1159 | 57.7 / 62.2 | 22.4% |
| wide5 H4dist≥p50 | 1271 / 1025 | 58.3 / 62.5 | 19.2% |
| tight2 slope<p50 | 1499 / 1361 | 58.7 / 60.2 | 30.1% |

- Every wide variant lowers the BUY win rate (25% → 19–24%) and the TP count (67 → 45–61), so BUY net
  falls in most cells. Gains show only in single cells (e.g. wide4 ATR base $313) and never in all 4.
- tight2 raises the win rate (≈30%) but fails DD/minEq in 3–4 cells.
- Walk-forward pick: beats native at $200 (both views) and loses at $313 (both views), so it is not robust.

## Asia BUY block
- Fold-OOS: passes all 4 cells (e.g. stress $200 net 1389 vs 983, DD 70.8 vs 76.6%).
- 2023-24 (locked on 2026-11-01 from discovery only; window not used to choose it): passes all 4 cells,
  e.g. base $313 −181.6 vs −262.8, DD 84.1 vs 89.9%, minEq 60.3 vs 36.8, profitable months 7 vs 5.
  It still loses heavily there.
- Caveats:
  - The hours were found in-sample on discovery, so the fold-OOS is not clean for it.
  - The full-period discovery base $200 is worse: net 1879 vs 1945, minEq 156 vs 188 (path effect: SELL net 1049 → 877).
  - This is an entry filter that removes trades. It does not raise TP.

## Next step (owner decision) — superseded: holdout run below, FAIL
Asia block was the only candidate. Clean tests left at that time:
1. The sealed 2020-01..2022-12 holdout, run once. It is bound to the regime-filter research, so opening it needs owner approval.
2. A forward shadow log (≥8 weeks/60 trades, log blocked BUY signals) per research NOTES.

Neither is started. Limits: current swap applied to history (COST_INCONCLUSIVE); Exness tick
replay ≠ MT5 fills.

## Sealed 2020-22 holdout — HOLDOUT_FAIL (owner-approved, run once)

Owner approved opening the holdout ("Open holdout 2020-22"). Protocol was frozen before data contact:
[protocol.json](../../runs/c22-26b8-asia-holdout-2020-2022/protocol.json)
(sha256 `776ca986…df12`). Input: 36 sealed zips, sha-verified, 73,374,873 ticks, 69,115 M15 bars.
**The holdout is now consumed. No retune on 2020-22.**

| Cell | native net / DD / minEq / +months | asia_block | gate |
| --- | --- | --- | --- |
| base $313 | −294.35 / 95.30% / 18.65 / 6 | −294.34 / 94.78% / 18.66 / 6 | pass |
| stress $313 | −294.44 / 95.32% / 18.56 / 3 | −295.08 / 94.97% / 17.92 / 2 | FAIL net, minEq, months |
| base $200 | −182.12 / 94.03% / 17.88 / 4 | −182.43 / 94.25% / 17.57 / 3 | FAIL all 4 |
| stress $200 | −179.96 / 93.30% / 20.04 / 4 | −179.55 / 93.29% / 20.45 / 2 | FAIL months |

Asia block: **FAIL**, no different from native (cent-level deltas). Do not adopt.

### Larger finding: native 26b8 has no edge in 2020-22
- Every cell loses 90–95%, mostly in 2020. After that the 10% cap rejects nearly everything
  (≈750–1,000 cap rejections), so 2021-22 is barely tested in the capped account.
- Diagnostic (not gating): native with a $100k balance, so the cap never binds, at fixed 0.01:
  573 trades, net −$504.87, **avg −0.113R/trade**.

| Year | SELL n / avgR / win | BUY n / avgR / win |
| --- | --- | --- |
| 2020 | 69 / −0.19 / 35% | 98 / −0.01 / 22% |
| 2021 | 167 / −0.18 / 34% | 60 / −0.31 / 13% |
| 2022 | 160 / +0.07 / 44% | 79 / −0.26 / 13% |

- 26b8 is now negative in both windows outside its selection period: 2020-22 and 2023-01..2024-08
  (−84..−92%). Its positive record is only 2024-09..2026-10, the strong-trend window it was chosen on.
- This is evidence of regime dependence or selection overfit in the strategy itself, beyond any TP/BUY tuning.
- The live Demo trial continues to run under owner authority. A strategy-level review of 26b8 is
  recommended before any real-money consideration (real money remains PROHIBITED).
- Limits: current swap applied to 2020-22 (COST_INCONCLUSIVE); Exness tick replay ≠ MT5 fills.
