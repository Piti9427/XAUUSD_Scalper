# Losing-trade diagnosis and volatility-floor LOYO: verdict (2026-11-13)

This document is research only. It does not change any runtime, VM, config or commit.

- **Baseline:** the selected candidate `sell3R_risk25.0_BE05_veto` on a $200 account. See [handoff](2026-11-13-c22-optimize-implementation-handoff.md).
- **Code and outputs:** `runs/c22-losing-trades-diag-2026-11-13/` (gitignored).
- **Costs:** every run uses base+swap and stress+swap. The cost status remains COST_INCONCLUSIVE.

## Phase 1: feedback loop
Command:
```bash
PYTHONPATH=. .venv/bin/python runs/c22-losing-trades-diag-2026-11-13/loop.py --parity
```
- It replays the candidate per segment and view. A cell is RED when net < 0.
- It asserts parity against the stored immutable cells, matching both net and trade count.
- Runtime is about 3 s per cell.

**Result: `RED_CELLS 10` out of 14.** Every 2020–2024a cell is red in both views. 2024b25 and 2026 are green.

## Decomposition of the losing years (`red_cand.txt`)
- The edge is negative before costs in most red cells:
  - BUY gross < 0 in 2021–2024a;
  - SELL gross < 0 in 2020, 2021 base and 2024a.
- Costs turn small positive gross results into losses:
  - 2020 BUY base: gross +133.5 → net −3.3 after spread −94 and swap −43;
  - 2021 SELL stress: gross +18 → net −99.
- At $200 in stress, the cap admission path dominates. 2022S has 449 virtual risk-cap rejects and 58 trades. 2026S has 413 rejects and 35 trades.

## Hypotheses tested
| # | Hypothesis | Probe | Result |
| --- | --- | --- | --- |
| H2 | Spread/R separates losers | `probe_cost.py` | **Falsified.** Range years lose even when spread/R ≤ 0.02 (base −81.6, n = 40). |
| H1 | Low $risk = no edge | `probe_cost.py` | Separates (range ≤ $6: −382 base; trend +19), but that is a price-level proxy for calendar time. |
| H1' | Low stop% (2.5·ATR/close) = no edge | `probe_cost.py`, `probe_volfloor.py` | Partial. Stop% < 0.3 trades lose in range years, but also include winners in 2024b25 Q4 and 2026-08..10 stress. |

## Frozen LOYO (protocol sha256 `e145efbd…6fa9e`): **FAIL**
- **Catalog:** volatility floor ∈ {0.2, 0.25, 0.3, 0.35}% × side ∈ {both, BUY-only}. The virtual-native veto stays on in every spec.
- **Selection:** the existing train-only `select()`, against the candidate baseline. It requires that no training cell gets worse.
- **Outcome:** every spec regresses at least one trend cell (2024b25 or 2026 stress). Six of seven folds fall back to the candidate, and held-out fails.

| Spec | Range years sum, base / stress | Trend years sum, base / stress |
| --- | ---: | ---: |
| candidate | −570 / −808 | 1683 / 799 |
| floor0.3_both | −237 / −288 | 1657 / 727 |
| floor0.35_both | −183 / −221 | 1340 / 818 |
| floor0.3_buy | −320 / −538 | 1675 / 718 |

**Attribution, floor 0.3 vs candidate:**
- **Gate measure verified.** `250·atr/close` equals the ledger's actual stop% for admitted trades (ratio 0.995–1.002 in 2021 base and 2026 stress).
- **2024b25 base:** 89 trades are removed, worth a combined +26.1, and all of them sit below the floor. The floor blocks them directly.
- **2026 stress:** 11 trades are removed, worth a combined +101.9.
  - Only 2 are blocked directly by the floor: 2026-08-14 BUY and 2026-10-19 SELL, worth a combined +46.7.
  - The other 9, worth +55.2, are a $200 cap knock-on. Losing the 08-14 winner lowers equity, so the candidate's own 10% cap then rejects 9 later winners.

**Post-hoc only** (not in the protocol, so it cannot support a claim). A continuous $200 account from 2020:

| Spec | Base final | Stress final | Max DD, base / stress |
| --- | ---: | ---: | ---: |
| candidate | $42.7 | $42.1 | 85.7% / 85.7% |
| floor0.3_both | $78.9 | $112.6 | 75% / 62% |
| floor0.35_both | $109.6 | $144.5 | 68% / 54% |

Every row still ends below $200.

## Conclusion
- The root cause of losses in 2020–2024a is that the 26b8 entry edge is negative or zero in a low-volatility, range regime. Costs make it worse.
- A volatility floor cuts range-year losses by about 58–73%. At 0.3 the cut is 58% in base and 64% in stress; at 0.35 it is 68% in base and 73% in stress. It also removes some low-volatility trend-year winners, which violates "nothing may get worse".
- No frozen spec passes, and no rule makes the range years profitable.
- A derived iteration would need regime identification to keep trend-year low-volatility trades. Entry regime filters already failed LOYO (2026-11-12), so that iteration is not run.

## Owner decision options
1. Keep the candidate and stop tuning entries and filters.
2. Accept the trade-off by relaxing the no-regression rule: floor0.3_both or floor0.35_both, giving up 2026 stress winners. That would need a new protocol, owner approval and a forward shadow.
3. Collect fresh forward data. All the history has now been seen.

## Owner relaxed rule (2026-11-13): trend give-up ≥90% of candidate: **FAIL**

Owner chose "ลอง vol floor ต่อ" with trend (2024b25+2026) allowed down to 90% of the candidate per view.
This is POST-HOC: every cell was seen before the threshold was chosen.

### Relaxed protocol (sha256 `e9b8f43a…0f97`, `runs/.../frozen-volfloor-relaxed/`)
- Reuses the hash-bound e145efbd cells. Per-fold select: training trend sum ≥ 0.90×candidate in both views, maximise min-view range gain.
- Verdict: held-out path trend ≥ 0.90 and range > candidate per view, plus continuous $200 final/maxDD/minEq vs candidate.
- All-7 selection: floor0.3_both. Folds: floor0.3_both in 6/7; 2024b25 fold → floor0.25_buy.

| Held-out path | Trend ratio | Range sum vs candidate |
| --- | ---: | ---: |
| base | 97.1% ✓ | −237 vs −570 ✓ |
| stress | **74.9% ✗** | −289 vs −808 ✓ |

Continuous $200 (floor0.3_both): base $78.9 vs $42.7, stress $112.6 vs $42.1; maxDD and minEq better ✓. Candidate continuous parity reproduced.

**Attribution.** In the 2024b25 fold the only training trend cell is 2026 stress, where the candidate makes just +24.9.
floor0.3_both makes −77 there (2026-08-14 BUY winner blocked → $200 cap knock-on), so the 90% ratio rejects it;
the fold falls back to floor0.25_buy, which loses 98 in held-out 2024b25 stress (675 vs 774). The ratio on a near-zero
2026S denominator plus the cap knock-on is the failure mechanism.

### Derived iteration 1/1 (sha256 `5137c758…5021`, `runs/.../frozen-volfloor-derived/`): **FAIL**
- Mechanism change from attribution: SELL-only floor {0.25, 0.3, 0.35} (keeps BUY winners). Criteria unchanged.
- SELL-only floors still make 2026 stress −33 to −45 (2026-10-19 SELL winner blocked → knock-on) and cut range loss far less
  (range sum base −475 to −496 / stress −502 to −641, vs candidate −570 / −808; floor0.3_both −237 / −289). Selection unchanged → same FAIL.
- Iteration budget used up.

**Conclusion unchanged.** Any vol floor that cuts range-year loss blocks at least one 2026 winner, and on a $200 account
the 10% cap amplifies that into multi-trade knock-on. The floor improves the continuous $200 path but still ends below $200.
Only fresh forward data can decide; history cannot.
