# 26b8 losing-year fix: leave-one-year-out verdict (2026-11-12)

**Goal (owner):** use what we know about where 26b8 loses, tune so those years stop losing, and test the result on real tick data plus the forward window.

**Method.** Every year has already been seen, so a plain backtest of a tuned rule only measures fit. Instead each test is leave-one-year-out (LOYO):
- pick the rule using 6 yearly $313 accounts;
- score it on the 7th year, which the pick never saw;
- rotate through all 7 years.

The sum of the 7 held-out years is the honest estimate. Protocols were frozen before the runs. Code and results are in `runs/c22-26b8-regime-fix-2026-11-12/` (gitignored).

## Root cause of the losing years (native 26b8, base, $313 per year)

- Losses in 2020–2024a come from **both sides**. BUY TP rate is 13–22% (needs > 25% at 3R). SELL TP rate in 2020/2021 is about 35% (needs > 43% at 1.35R).
- In the screen (`screen.py`), each entry feature was split into quartiles. The best quartile is still ≤ 0 in every range year. So an entry filter can only shrink range-year losses; it cannot make those years profitable.

## v1: entry regime filters (protocol `7d799829…7112`) → **FAIL**

- Candidates were per-side low-cut filters on h4slope, h4dist, d1dist, e50slope and er96.
- Thresholds were set at p10/p25/p40 of the training-year signal bars, so the held-out year never informed them.

| | native | filter (LOYO held-out) | filter (fit on all 7, in-sample) |
| --- | --- | --- | --- |
| Sum base | 1,097 | **889** | 1,512 |
| Sum stress | 390 | **202** | — |
| Held-out years improved | — | **1 / 7** | — |

- In-sample the filter looks like a fix (+$415, 2026 +$344). Out of sample it is worse in 6 of 7 years. That is textbook overfit.
- Root cause:
  - Out of sample, the filters remove TP trades about as often as SL trades. For example, 2026 removed 20 SELL TPs (−$593) against 17 SLs (+$516).
  - The freed slots then let replacement losers in.
  - The pick was unstable: 4 different feature combinations across 8 folds.

## v1b (derived): risk/exit mechanics (protocol `cf03fb50…aff7`) → **PASS**

- Catalog: the loop2 risk mechanics (B2 tick BE, maxloss, side/range loss rules), from cached cells.
- Each fold picks the best candidate on its 6 training years. `B2+maxloss_1` was picked in 6 of 7 folds; the 2024b25 fold picked `B2+range1`.

| Held-out year | native base | pick base | native stress | pick stress |
| --- | --- | --- | --- | --- |
| 2020 | −182.65 | −177.83 | −255.42 | −225.62 |
| 2021 | −213.36 | −118.87 | −203.26 | −139.38 |
| 2022 | −23.59 | **+98.31** | −147.14 | **+17.64** |
| 2023 | −102.71 | −86.01 | −180.21 | −139.54 |
| 2024a | −173.88 | −19.36 | −203.54 | −120.55 |
| 2024b25 | 906.07 | 822.60 | 740.40 | 589.81 |
| 2026 | 887.35 | 762.62 | 638.72 | 624.91 |
| **Sum** | **1,097** | **1,281 (+17%)** | **390** | **607 (+56%)** |

- 5 of 7 years improve, and every range year loses less. 2022 turns positive.
- Trend years give some back (−$84 / −$125) because maxloss_1 blocks winners after the first loss of the day.
- Worst-year DD falls from 80% to 63%.
- Forward 2026-10-24..11-11:

  | Account / view | native | B2+maxloss_1 |
  | --- | --- | --- |
  | $313 base | +48.01 | +48.01 |
  | $313 stress | +47.13 | +47.13 |
  | $1,845 stress | +9.11 | +47.13 |

  There are too few trades to decide.

## Verdict

- Entry filters do not generalize. Do not adopt one.
- Risk mechanics do generalize under LOYO. `B2+maxloss_1` stays the candidate.
- No rule tested makes 2020, 2021, 2023 or 2024a profitable. That needs a different entry edge, not tuning.
- Limits:
  - Both catalogs were designed after seeing all years. LOYO guards the selection, not the design of the catalog.
  - The forward window has too few trades.
  - Any adoption goes through forward observation, a new RulesID and owner approval.
  - Real money stays prohibited.
