# C22: the passed candidate evaluated at the live balance (2026-11-18)

**POST-HOC exploratory.** Every history window has already been seen. The frozen forward shadow (15bda721) is unchanged.
- Code: `runs/c22-candidate-livebal-2026-11-18/` (`fwd_livebal.py`, `hist_livebal.py`, plus JSON outputs).
- Candidate: `sell3R_risk25.0_BE05_veto`. For a SELL whose initial risk is ≥ $25, TP becomes 3R and BE moves at 0.5R. Entries are vetoed to native admissions. Everything else is native.

## Why
- The candidate was selected on $200 books. At $200, the 10% cap rejects SELLs with risk > $20, so the ≥ $25 band almost never fires.
- The demo account trades at about $313–$405, where the band does fire.
- The $200 shadow therefore reports NOT_EXERCISED for exactly the trades the live account takes.

## Method
- Each book starts from a warm-up replay to the first tick + 5 min (asserted trade-free). The carry-state balance is then overwritten.
- Parity guard: at $200, the split run equals the unsplit native run (2020 base −133.92). The forward window at $200 equals the frozen shadow report (+27.68, 8 trades).

## Forward window 2026-10-24 .. 11-16 (br474 swap)
| Balance | View | Native net / DD | Candidate net / DD |
|---|---|---|---|
| $313 | base | +99.65 / 24.0% | **+127.38 / 19.1%** |
| $313 | stress | +98.72 / 24.1% | **+126.51 / 18.9%** |
| $360 | base | +99.65 / 21.6% | **+127.38 / 17.3%** |
| $360 | stress | +60.70 / 29.8% | **+88.49 / 25.1%** |

- The entire difference comes from **one trade**: 2026-10-30 17:15 SELL, risk $27.6.
  - Native hit the full SL, −27.7.
  - The candidate moved to BE at +0.5R and exited at −0.01.
- n = 1, so this is illustration, not evidence.

## History, 7 independent yearly books at $313
| Segment | Base: native → candidate | Stress: native → candidate |
|---|---|---|
| 2020 | −182.65 → **−200.49** (DD 67.2 → 67.9) | −255.42 → −253.55 (DD 85.5 → 82.9) |
| 2021–2024b25 | identical (no SELL with risk ≥ $25 at those gold prices) | identical |
| 2026 | +887.35 → **+1271.72** (DD 43.0 → 33.7) | +638.72 → **+1100.26** (DD 51.9 → 35.8) |

**Mechanism in 2026 base (43 changed trades, net +384):**

| Change | Trades | Effect |
|---|---:|---|
| Native SL → vetoed | 11 | Losses avoided because the position was still running the 3R target |
| Native TP → candidate SL | 9 | Mostly small losses after a BE move. This is the cost |
| Native TP → vetoed | 8 | Wins lost |
| Native TP → candidate TP | 9 | Larger wins (3R) |
| Native SL → candidate SL | 5 | Unchanged outcome |
| Native TP → end of sample | 1 | Still open when the window ended |

**2020 base fails the owner's no-regression rule** by −17.84:
- A native TP of +35.02 becomes −8.24.
- A native SL of −25.45 becomes −0.03.

## Reading
- This is the one statistically selected mechanism that really cuts SL damage ("lose less"). It moves to BE at 0.5R on large-risk SELLs.
- The benefit is large in a trend regime (2026). It is neutral when gold prices keep risk under $25. It is slightly negative in 2020 base.
- It is still post-hoc and fails one cell (2020 base) under the strict rule. Adoption needs an owner decision and the online virtual-book runtime, which is not built. See `2026-11-13-c22-optimize-implementation-handoff.md`.
- The frozen $200 shadow cannot test it. A forward profile at the live balance would have to be frozen *before* the December data.

## Frozen live-balance forward shadow (2026-11-18)
- Location: `runs/c22-forward-shadow-livebal-2026-11/`. Protocol sha256 `a724f10ce7ec992138b1d31af8463f1637ffa4a0d2deafb3f00d3afc04cd03e4`.
- **Window:** starts 2026-11-17T00:00Z. That is after the last seen quote (11-16 23:59:58Z), so it covers unseen data only.
- **Books:** primary live360, sensitivity live313. Views: br474 base and stress.
- **Maturity:** at least 28 days, at least 20 native trades, and at least 5 native SELL trades with risk of $25 or more.
- **Verdict:** NOT_EXERCISED, FORWARD_CONSISTENT or FORWARD_INCONSISTENT, against native, with net and maxDD both required in both views.
- **First run:** VERDICT NO_DATA (`reports/2026-11-17-892cce21e155.json`), as expected.
- **Schedule:** the monthly task `c22-forward-shadow-monthly` now runs this shadow after the $200 shadow. The first real data comes after the 2 Dec refresh.
