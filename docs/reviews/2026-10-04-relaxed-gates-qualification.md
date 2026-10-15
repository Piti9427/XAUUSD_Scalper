# Qualification Review: Relaxed Gates & Qualified Candidates

**Execution Date:** 2026-10-04  
**Audit Script:** `docs/reviews/artifacts/rescreen_relaxed_gates.py`  
**Verdict:** **QUALIFIED** (10 candidates pass all 6 joint scenarios)

---

## 1. Executive Summary

Following owner authorization on 2026-10-04 to relax the research drawdown ceiling to $\le 35\%$ and half-window trade minimum to $\ge 10$, a comprehensive re-screening of all archived candidate results across 28 evaluation runs was performed.

Out of over 4,000 evaluated parameter combinations, **10 configurations achieved full qualification across all 6 scenarios** (Full Base/Stress, First-Half Base/Stress, Second-Half Base/Stress).

The primary recommended winner is **Reward156** (`RESEARCH-HYBRID-RSI7BUY-D48SELL-T156`):
- Full Base Net: **+$883.77** (vs Trial30 baseline +$465.32) — **+90% improvement**
- Full Base DD: **22.50%** (vs Baseline 26.01%) — **lower risk**
- Full Stress Net: **+$742.03** (vs Baseline +$361.40) — **+105% improvement**
- Second-Half Stress Net: **+$335.64** (vs Baseline +$12.17) — **stabilized choppy regime**
- 152 executed trades (23 BUY / 129 SELL) — genuine bidirectional execution.

---

## 2. Re-Screen Summary Across Catalogs

| Result Source | Total Rows | Qualified Under Relaxed Gates | Near-Misses ($\le 3$ fails) |
|---|---:|---:|---:|
| `2026-10-03-hybrid-reward-results.json` | 594 | 3 (Trial 156, 288, 310) | 16 |
| `2026-10-03-hybrid-reward-admission-results.json` | 324 | 1 (Trial 235) | 67 |
| `2026-10-03-reward-session-results.json` | 108 | 3 (Trial 37, 55, 61) | 8 |
| `2026-10-03-hybrid-parent-horizon-corrected-results.json` | 192 | 1 (Trial 123) | 6 |
| `2026-10-03-hybrid-parent-trend-results.json` | 288 | 2 (Trial 171, 179) | 6 |
| Other 23 files | ~2,500 | 0 | 0 |
| **Total** | **~4,000+** | **10** | **103** |

---

## 3. Comparison of Top Qualified Candidates

| Candidate | Catalog / Trial | Full Base Net / DD | Full Stress Net / DD | 2nd Base Net / DD | 2nd Stress Net / DD | Key Parameter Difference |
|---|---|---|---|---|---|---|
| **Reward156** (Primary) | `hybrid-reward` T156 | **$883.77** / 22.50% | **$742.03** / 33.97% | $370.61 / 34.45% | $335.64 / 34.72% | All-session, RSI7/35 BUY + D48 SELL, Target 1.35R, BUY pause 5% |
| **Session37** | `reward-session` T37 | $885.80 / 25.19% | $730.35 / 32.22% | $225.26 / 33.46% | $190.37 / 33.72% | Avoid rollover session (UTC $\ge 21$ entry skip) |
| **Reward288** | `hybrid-reward` T288 | $760.36 / 23.27% | $627.03 / 34.58% | $242.88 / 33.53% | $161.88 / 33.81% | RSI14/35 BUY |
| **Reward310** | `hybrid-reward` T310 | $742.58 / 23.83% | $634.97 / 34.58% | $137.96 / 32.71% | $102.61 / 33.23% | RSI14/35 BUY, BUY pause 10% |

---

## 4. Implementation & Parity Evidence

1. **Clean Strategy Implementation:** `reward156_bars(completed)` added to `scripts/strategy.py`.
2. **Deterministic Parity:** `tests/test_reward156_strategy.py:test_research_signal_parity` verified 100% direction match (0 signal divergence) against `scripts/research/campaign_signals.py:candidate_frame`.
3. **Execution Safety Invariants:**
   - Single-position only; no martingale or recovery baskets.
   - Fixed 0.01 lot sizing; 10% risk cap rejects trades if equity is too low.
   - 20% daily loss limit halts new admissions for the remainder of UTC day.
   - Timezone-aware UTC DatetimeIndex mandatory.
