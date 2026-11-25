# Equity-based sizing research — verdict (2026-11-12)

**Verdict: keep fixed 0.01 lot. No risk-target % passes the frozen rule.** Plan Track B; protocol
`runs/c22-sizing-2026-11/protocol.json` (sha256 `63e688ff…0e5a`), frozen before running.

- Sizing: `('ff', f)`, lot = max(0.01, floor(f·balance ÷ risk per lot)). The 10% cap and margin are re-checked,
  and the lot is never rounded up.
- Accounts: 7 independent yearly $313 accounts, base+swap and stress+swap.
- Parity: the engine with no sizing knob equals native in 14/14 cells; tiny f equals fixed 0.01 in all cells.

## Results (native 26b8 decides)

| Grid | Base mean $/mo | % +months | Worst-year DD | Min equity | Stress mean | Rule |
| --- | --- | --- | --- | --- | --- | --- |
| fixed 0.01 | 13.89 | 46.8 | 80.2% | $74.10 | 4.93 | fails DD/minEq (kept as default) |
| 2.5% | 13.50 | 48.1 | 83.2% | $62.88 | 4.23 | FAIL |
| 5% | 18.23 | 41.8 | 95.1% | $20.19 | 3.81 | FAIL |
| 7.5% | 46.68 | 39.2 | 95.7% | $19.14 | 11.27 | FAIL |

B2+maxloss_1 (information only): fixed gives $17.45/mo with worst DD 63%. 7.5% gives $54.67/mo with DD 94%.
Every % fails.

## Root cause
- **The edge is negative in 2020–2024**, so lot growth compounds losses. Native 7.5% loses $261–$291 per range
  year (DD 87–96%), but makes +$3,266 in 2024-09..2025-12 against +$906 fixed.
- **"Same risk %" is not the same as fixed 0.01.** In low-volatility years (2020–23, gold around $1,800–2,000),
  0.01 lot risks only about $5–10 (2–3% of $313). Even the 2.5% target scales to 0.02–0.03 lots, which is more risk
  than today. At 2026 prices, 0.01 already risks $18–36 (6–10%), so the % targets add little there.
- Fixed 0.01 itself fails the DD ≤ 40% / minEq ≥ 50% bars in range years. Sizing cannot fix that.

## Implication
Sizing becomes useful only once the strategy's edge holds across regimes. That is a strategy-level problem,
not a sizing problem. The priority for more $/month at the same risk stays with **availability** (Track A):
capturing 14/14 signals instead of 3/14.
No contract, config or VM change.
