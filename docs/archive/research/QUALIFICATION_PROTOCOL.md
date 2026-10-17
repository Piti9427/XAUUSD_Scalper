# BotTradeGold qualification protocol (decision draft, 2026-09-23)

This protocol concerns **selection for a Demo strategy bot**, not authorization for real-money trading. ADR-0030 fixes the evidence boundary. No candidate currently qualifies. The 2010–2026 research data and retrospective walk-forward results were already exposed during strategy development, and their USD/1-oz results omit unmeasured Exness execution costs; they may nominate challengers but cannot certify them.

## Frozen candidate set

The candidate universe remains the 17 documented families and sourced variants (120 baseline specs plus five separately declared handoff parameter configurations, deduplicated by full contract). Do not add an unreferenced SL/TP/filter grid. Treat reconstructed rules as new versioned contracts; never claim parity with lost original implementations. Freeze exact entry, exit, signal timing, risk, instrument, code/config hashes, selector, and this protocol **before** the first qualifying tick. Any material rule or execution-model change starts a new contract and a new prospective validation period.

Pre-freeze 2010–2025 Bid/Ask M1 research selected three **Validation Challengers** for falsification, not Demo promotion:

| Contract | Native net USD/1 oz | Trades | Positive years | Known weakness |
| --- | ---: | ---: | ---: | --- |
| `GSS_OTE__h1structure` | +76.28 | 155 | 9/16 | 2024–2025 net −54.35; low frequency |
| `Donchian20_H4` | +378.08 | 1,358 | 8/16 | Short net −1,330.98; best positive year contributes 51.2% |
| `AsianRetest__h1ema` | +275.65 | 1,131 | 8/16 | Long net −7.24; best positive year contributes 51.8% |

These are **not** `REVIEW_CANDIDATE` under the repository's older research screen. The table is descriptive and cannot be counted toward prospective qualification. Source: audited baseline `annual.csv` and native trade logs from the pinned Dukascopy-derived M1 run; 2026 partial year excluded.

## New evidence and execution model

1. Bind the run to the current Exness Demo account identity and the gold symbol returned by that terminal. Capture account currency/balance/equity, symbol contract size, tick size/value, volume minimum/step, trading hours, stops rules, and fee/swap terms with timestamps. A changed account type, server, or symbol is a new validation target.
2. A read-only Shadow monitor captures and hashes post-freeze UTC Bid/Ask real ticks and records candidate signals. The first implementation records **signals only**; it does not simulate fills or produce P&L. A later tick-level execution replay must record order lifecycles before qualification. Shadow mode never calls `order_send`. Audit quote ordering, duplicate/missing ticks, crossed markets, market closures, signal-bar completeness, and replay parity. Missing tick coverage during an entry/exit window makes that trade unscorable and the affected test inconclusive; do not synthesize ticks or fills.
3. Simulate the target account's starting capital and broker-valid lot constraints, risking at most 0.5% of the lower balance/equity per admitted setup. Floor to valid lot steps, reject insufficient capital, and keep each frozen contract's own exit rules. Calculate account-level marked-equity drawdown from the continuous prospective ledger, including rejected-setup counts; the old per-1-oz annual drawdown is not comparable.
4. Use observed Bid/Ask prices for base execution. Calibrate commission, fee, swap, requested-to-filled price deviation, latency, and rejection behavior from actual target-account Demo deals matched by order type, entry session, and side. Sessions are London 07:00–10:30 UTC, New York 12:30–16:30 UTC, and Other; do not infer DST. A separately approved bounded Demo fill experiment may collect missing evidence; it is not strategy automation. Require **at least 59 independent fills per stratum actually used**. Under an independent, same-distribution assumption, the largest observed adverse slippage is a distribution-free upper bound for that stratum's 95th percentile at 95% confidence (`0.95^59 < 0.05`). The three old ledgers span six market-order/session/side strata, implying at least 354 matching fills if all remain active prospectively. Audit clustering and account/broker-condition changes before applying that bound. Missing or non-representative strata keep the cost gate `INCONCLUSIVE`; never replace them with fabricated zeros.
5. Re-run the same frozen strategy on the tick ledger with observed base costs and a transparent twice-cost scenario, preserving trade identity and every rejection. Base P&L already pays observed Bid/Ask spread; stress replays quotes at twice their observed spread around the observed midpoint and charges twice the measured non-spread fees, swap, and stratum upper-bound adverse slippage. Do not charge spread twice in base P&L or assume a favorable fill.

## Pass, ranking, and portfolio rule

Each challenger is assessed once on post-freeze data. Require at least 100 broker-valid simulated closed trades; base PF ≥1.50; positive net expectancy; continuous account max drawdown ≤5%; positive lower weekly-block bootstrap expectancy; non-negative long, short, London, and New York slice expectancy; and positive expectancy with PF >1.0 under twice measured costs. Use the existing ADR-0025 qualification policy as the starting implementation, adapting its fixed-R drawdown and two-leg capital check to account-valid sizing and each contract's native exits. Missing slices, ticks, broker specifications, or cost calibration return `INCONCLUSIVE`, never PASS. Account P&L and R are both reported, with precise denominators.

Predeclare three standalone policies and six ordered primary/complement policies as the nine possible tests on the same prospective sample. Use the existing 10,000-draw, seeded weekly-block bootstrap convention and a Bonferroni lower-tail quantile of `0.025 / 9` for positive expectancy and paired incremental expectancy claims; report the unadjusted 2.5% lower bound beside it. This correction is conservative and must be applied before picking a winner. If more than one standalone policy passes, choose primary by the highest adjusted lower confidence bound of expectancy under twice measured costs, then lower drawdown, then more trades. If none passes, choose none; do not tune on the validation sample and call the rerun independent.

At most one complementary strategy may be added. Replay the combined policy with **one open position per symbol** and primary signals taking priority; the complement trades only while flat. The combined policy must pass the same gate and show a positive paired weekly-block lower bound for the incremental cost-adjusted expectancy while its max drawdown does not exceed the primary-only drawdown. Otherwise use the primary alone. Qualification for Demo automation still does not establish forward-Demo or real-money readiness.

## Required outputs and acceptance

- Immutable manifest: contract/config/code hashes, account/symbol identity, tick/deal source hashes and coverage, freeze timestamp, exact cost derivation, scorer version, and `COMPLETE` written only after ledger reconciliation.
- Matrix: all three challengers plus eligible combined policies, base/stress net and R, PF, account drawdown, confidence intervals, monthly/session/direction breakdowns, costs, rejects, and `PASS`/`INCONCLUSIVE`/`REWORK` reason codes. No row may imply guaranteed future profit.
- Tests: tick UTC/identity/gap handling; no `order_send` in Shadow mode; signal/replay parity; spread and cost accounting; lot-step floor and small-account rejection; account-equity drawdown; bootstrap determinism and multiple-testing correction; primary precedence and one-position rule; manifest/trade-log reconciliation.

**Not yet proven:** target-account real-tick availability and continuity, representative fill-cost evidence, and enough new trades. Until those checks pass, current result remains **no Demo Bot Candidate**.

The current read-only capture and signal-audit commands, with their limits and evidence checks, are documented in [SHADOW_MONITOR.md](SHADOW_MONITOR.md). This implementation does not satisfy the execution replay or qualification gate above.
