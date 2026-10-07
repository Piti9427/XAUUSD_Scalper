# B1 profit challenger research — 2026-09-26

## Verdict

No challenger earns promotion. B20 won the pre-primary selection but failed the later primary evaluation. Retain B1 as research baseline; no runtime configuration changed and no broker orders sent. This is not production approval.

## Scope and model

Eight declared challengers, B1 baseline and MR2 comparator; five windows × two cost reserves = 100 rows, each with raw fixed-R and DD-sized replay (200 simulations). Public GetData M15 data contains 15,485 bars, February 2–September 25, 2026; common warm-up begins February 12 at 20:00 UTC. This is about 7.4 months, not a year.

The latest handoff baseline uses Donchian30, RSI14 caps 75/25, SL 2.5 ATR and TP 3.5R. This supersedes the earlier conversational RR 2.5 proposal for this experiment only. Ideal proportional $100 sizing has no minimum lot. Costs are 0.10R and 0.15R proxies, not measured broker spreads/fees. DD uses M15-close equity versus high-water mark. Risk tiers 1%, 0.75%, 0.5%, 0.25% at DD thresholds 3%, 6%, 9%; hard-stop latch at 12%. These are handoff rules, not an 8% acceptance claim.

Next observed M15 open entry; unresolved simultaneous SL/TP uses SL first; stop gaps execute at adverse open, TP gaps at target. Window-end open trades are marked at end. Monthly fresh runs reset state and cannot be summed as one portfolio.

## Declared changes

- **B20:** Donchian 20 only; other B1 rules unchanged.
- **B40:** Donchian 40 only; other B1 rules unchanged.
- **P1:** EMA20/50 pullback from unfinished prior experiment; original exact rules, B1 exits.
- **B1_H1:** B1 long only if completed H1 close>EMA200 and slope>0; short inverse.
- **B1_BODY:** B1 direction-aligned candle body >=50% of candle range.
- **B1_SESSION:** B1 signal close UTC in [07:00,17:00).
- **B1_SL2:** B1 stop 2 ATR instead of 2.5; target remains 3.5R.
- **B1_TP25:** B1 target 2.5R instead of 3.5; stop remains 2.5ATR.

## Selection before primary

Discovery: February 12–June 25, split at May 1. Qualification at both costs: at least 30 trades, PF ≥1.1, positive sized return above B1, DD no worse than B1 and below 12%, no hard stop. Each inner block at 0.15R also needs ≥10 trades and positive total R. Rank by pre-primary sized return at 0.15R, then lower DD and name. Selection file was written before primary scoring.

B20 and B1_TP25 qualified. B20 selected: discovery return +5.93%, DD 10.73%, versus B1 −1.28%, DD 11.29%. No selection changed after viewing primary. Primary had been exposed in prior work: it is a retrospective later evaluation, **not pristine OOS**.

## Primary results: June 26–September 25, 2026

Ideal $100, cost reserve 0.15R. PF and expectancy use raw fixed-R trades; return/DD use tiered position sizing. Their signs can differ because exposure changes over time. Hard-stop variants can have fewer sized trades.

| Strategy | Raw / sized trades | Expectancy R | PF | Sized return | Close-equity DD | Stop |
|---|---:|---:|---:|---:|---:|---|
| B1 | 87 / 87 | 0.091 | 1.110 | +6.84% | 10.31% | False |
| MR2 | 37 / 37 | 0.080 | 1.107 | +0.17% | 8.37% | False |
| B20 | 96 / 96 | -0.072 | 0.918 | -8.23% | 10.90% | False |
| B40 | 82 / 82 | -0.052 | 0.940 | -9.14% | 10.79% | False |
| P1 | 73 / 73 | 0.093 | 1.113 | +1.73% | 9.20% | False |
| B1_H1 | 64 / 59 | -0.236 | 0.743 | -8.82% | 12.07% | True |
| B1_BODY | 78 / 78 | -0.054 | 0.938 | -2.86% | 10.45% | False |
| B1_SESSION | 63 / 49 | -0.293 | 0.685 | -9.90% | 12.05% | True |
| B1_SL2 | 110 / 110 | 0.077 | 1.092 | -8.06% | 9.78% | False |
| B1_TP25 | 117 / 117 | 0.046 | 1.061 | +3.09% | 9.85% | False |

None of eight challengers exceeds B1 primary sized return at either cost. At 0.10R: B1 +11.83%, B20 −6.03%, B1_TP25 +6.54%. TP2.5R increases trades but reduces primary profit; it does not establish a better strategy.

## Locked-candidate diagnostics

B20 trails B1 in all three fresh monthly windows at 0.15R: −3.02% vs +1.51%; −5.58% vs +5.22%; −4.36% vs −1.87%. Carrying equity/HWM from February gives primary B20 −5.02% versus B1 +11.66%. Neither reset choice rescues the selected challenger.

Paired weekly realized-R bootstrap: 20,000 seeded paths, 14 blocks including quiet days and final partial block. B20−B1 observed −14.85R; 95% interval [−51.15, +24.90]R; multiplicity-adjusted lower bound −64.45R. No positive-improvement evidence. This conditional diagnostic is neither future-profit probability nor broker-cost equity Monte Carlo.

## Exness captured-tick replay: simulated $100

Same primary date range, broker tick-derived bars and captured XAUUSDm contract: minimum/step 0.01 lot, contract size 100. B1: 378 signals rejected below minimum-risk sizing, zero trades. B20: 543 rejected, zero trades. No lot rounded upward to bypass risk cap. Public OHLC and broker tick data differ; signal counts are not expected to match. Historical commission/margin/swap completeness is not established; current captured swap specifications are a scenario. Zero trades cannot validate profitable execution.

## Verification

| Requirement | Observed evidence |
|---|---|
| Preserve baseline calculations | B1/MR2 primary counts, total R, return and DD exactly reproduce supplied confirmation |
| Causal candidate signals | Four prefix checks for all candidates |
| Accounting | All sized ledgers reconcile equity + budget × net R |
| Selection isolation | Four focused unit tests including primary contamination rejection |
| Repository regression | `python -m unittest discover -s tests`: 536 tests, OK |
| Artifact integrity | 100 unique rows, 300 ledgers, source/config/code/selection SHA-256 checks passed |

## Reproduce

Run from repository using a fresh output directory (existing outputs are rejected):

```bash
.venv/bin/python -m scripts.research.profit_challengers \
  --source /Users/nopparuj/.codex/.chatgpt-projects/g-p-6ab1758a2f8c8191977d3e419a8926ec/backtest \
  --output data/b1_profit_research_new
.venv/bin/python -m scripts.research.profit_challenger_checks \
  --research data/b1_profit_research_new \
  --capture data/b1_d_exness_ticks_2026_full_retry \
  --output data/b1_profit_checks_new
```

Artifacts: [metrics](../../data/b1_profit_research_2026-09-26/metrics.csv), [selection](../../data/b1_profit_research_2026-09-26/selection_locked.json), [results and hashes](../../data/b1_profit_research_2026-09-26/results.json), [diagnostics](../../data/b1_profit_checks_2026-09-26/diagnostics.json), [frozen contract](../../data/b1_profit_research_2026-09-26/contract.json). Original synced source remains read-only.

## Limits and next decision

Do not keep tuning against this primary period to manufacture a winner. Evidence needed next: genuinely unseen/longer data with different regimes and executable account sizing before a new frozen candidate evaluation. No MT5 Strategy Tester parity run or live EA execution was performed. Existing longer-history concerns are not overturned by this short sample.

Methodological reference: [Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf). Platform tester reference: [MQL5 testing documentation](https://www.mql5.com/en/docs/runtime/testing).
