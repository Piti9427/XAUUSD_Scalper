# C22 current Demo contract versus maximum-profit research — 2026-10-24

**Research profit leader wins this historical comparison: higher terminal net
profit and lower observed equity DD in all six matched cost/counter scenarios.
This does not qualify a Demo replacement or establish future profitability.**

Goal: compare the two existing contracts for terminal profit, MM/DD trade-offs
and bot compatibility. Simpler alternative used: audit existing pinned outputs
instead of adding parameters, increasing lots or launching another optimization.
No new economic replay, broker call, deployment or candidate adoption occurred.
The owner's pause on increasing lots remains in force.

## Comparable inputs and observed results

Both start200USD once on the same171,171,013 Exness XAUUSDm Bid/Ask ticks and
49,729 completed Bid M15 bars. Actual quote endpoints are
2024-09-01T22:05:06.129Z through2026-10-23T20:57:59.517Z; requested interval is
[2024-09-01,2026-10-24)UTC. Both retain profits, fixed0.01lot, single position,
initial cost-inclusive risk cap10%, daily10% entry gate and no recovery.
Both use the same swap model and named base, price-stress and fee-stress inputs.
The reported rows below use raw daily-loss counting; the separate cent-counter
sensitivity also preserves the net/DD winner in all three cost scenarios.

Base: current contract final407.17USD/net207.17USD, research final1697.58USD/
net1497.58USD. Research net is7.23times current, extra1290.41USD; observed equity
DD falls39.28% to34.80%, a4.48percentage-point reduction.

Price stress: current final394.02USD/net194.02USD, research final1263.10USD/
net1063.10USD. Research net is5.48times current; observed DD falls37.82% to35.71%.
Fee sensitivity: current net202.93USD/DD38.47%, research net1115.22USD/DD36.52%.
Each cost view includes modeled swap. Different cost views can admit different
trades, so fee stress outperforming price stress is not a causal fee benefit.

Base profit factor improves1.171 to1.342; expectancy1.59 to2.89USD/trade;
trades130 to519. Equivalent CAGR over actual quote duration is39.38% versus
171.54%, descriptive only; fixed lot does not compound exposure automatically.
Completed closing-balance peak-recovery interval decreases348.23 to100.40days.
That statistic is not continuous tick-equity underwater time or a future bound.

## Major — Better net/DD does not mean every risk measure improves

Finding: research trades a deeper capital trough and longer losing streak for
its larger final profit, despite lower peak-to-trough percentage equity DD.
Base minimum observed equity is155.96USD versus168.24USD current; longest losing
streak is9 versus5. Under price stress it is9 versus6.

Worst base cash loss is93.78USD versus47.47USD; worst realized netR is−2.128R
versus−1.350R. Stress worst netR is−2.133R versus−1.360R. Cash-loss comparisons
have different entry equities: max realized loss as a fraction of entry equity
is6.70% versus10.05% base, and9.14% versus9.75% stress. Neither cash loss nor
R alone establishes risk-of-ruin. Initial risk cap is not a guaranteed fill-loss
limit. Keep these diagnostics visible rather than reporting only the winning DD.

Evidence: independent source-bound ledger calculations in
[comparison.json](../../runs/c22-current-vs-profit-2026-10-24/comparison.json),
with pre-existing independent full-tick DD reconstruction of both raw base and
stress paths. New comparison assertions reconcile fixed lots, entry balances,
gross/net/commission/swap and final cash for12saved paths.

Suggested action: retain fixedlot and protection invariants; predeclare tail-loss
and recovery reporting for forward validation. Do not remove losing gap trades
or clamp stop results to−1R. No new DD threshold is imposed by this review.

## Major — Selected historical winner remains exposed to selection bias and costs

Finding: the research leader was discovered through74configurations on the same
history; repeated reconstruction establishes reproducibility, not an independent
profitability sample. The campaign explicitly sets `holdout=False` at
[campaign.py:165](../../runs/c22-terminal-growth-2026-10-24/campaign.py#L165).
Historical selection risk is discussed by the primary
[backtest-overfitting paper](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).
No PBO, p-value or calibrated risk-of-ruin is claimed here.

Base-to-price-stress net falls29.01% for research versus6.35% current. Research
still wins net in matched stress views, but modeled execution sensitivity is
material. This is a whole-account comparison, including changed admissions,
not a pure incremental-cost decomposition. Historical swap/calendar/commission,
HMR/stop-out and full session coverage remain unqualified; COST_INCONCLUSIVE.
Public ticks also cannot certify target-server parity:
[Exness tick-history documentation](https://get.exness.help/hc/en-us/articles/360021547851-Tick-history).

Suggested action: freeze a candidate and evaluation protocol before subsequent
unexposed observations; obtain dated broker economics and matched server data.
Keep discovery, coverage, cost and forward statuses separate.

## Blocker for adoption — Current Demo adapter does not execute research contract

Finding: research config is not a drop-in configuration for the current sender.
Current [C22H4Strategy:56](../../scripts/c22h4/runner.py#L56) fixes daily-loss-count1;
[protects:112](../../scripts/c22h4/runner.py#L112) enables protection only for SELL.
[BarCache:108](../../scripts/c22h4/strategy.py#L108) prepares the frozen contract;
[verify_sources:53](../../scripts/c22h4/strategy.py#L53) rejects contract/source drift.

Research changes RSI14cross25 toRSI7cross30, SELL96 to48bars, BUY SL1.5 to2ATR,
BUY protection off toBE1R, SELL target3ATR to1.35R and daily-loss-count1 to2.
This comparison verifies every current config contract field against the active
research control and every challenger config field against its source-bound cell.
The active control is a historical replay, not broker-confirmed Demo PnL.

Trace: [campaign prepared:60](../../runs/c22-terminal-growth-2026-10-24/campaign.py#L60)
calls [research prepare:84](../../scripts/research/c22_frequency_adapter.py#L84),
then canonical replay/entry. [prepare_entry:85](../../scripts/research/breakout_entry.py#L85)
keeps0.01lot for these fixed-sizing rules and checks risk/margin at104–108.
[replay:109](../../scripts/research/breakout_replay.py#L109) initializes200USD once;
[close:227](../../scripts/research/breakout_replay.py#L227) credits exits/swap to
the running account, with commission accounted in the lifecycle. Runtime takes
its own frozen-contract/broker lifecycle path; research parity is not assumed.

Suggested action: implement and verify a separate matching research adapter and
entry/protection/daily-policy parity before any adoption review. Retain current
Demo contract/source pins and existing cutover approval gates.

## Verification and integrity repair in this review

The first fresh campaign verifier stopped on a spec hash mismatch: a subsequent
discussion had been appended to the pinned campaign spec. The exact archived
spec bytes were verified against the original protocol hash and restored;
subsequent owner clarification was preserved separately in
[closure discussion](../../specs/c22-closure-discussion-2026-10-24.md).
No source pin, trading logic, ledger, result or protocol hash was changed.

After that repair, fresh campaign verification passed234economic cells and24
stored whole-result repeats, including current source/input/completion hashes,
cash/swap/risk/daily-guard checks. This checks existing results and repeats;
it is not234new replays or24new repeats in this turn.

Fresh focused comparison passed12existing full-account paths and6matched
cost/guard comparisons; verified risk-review artifact hashes and both config
identities. The earlier108focused runtime/replay tests remain earlier evidence;
no new runtime test suite or broker connectivity check was needed for this
read-only strategy comparison. Comparison code and machine evidence stay under
[ignored run directory](../../runs/c22-current-vs-profit-2026-10-24/).

The comparison Canvas embeds the exact audited JSON; all324monthly data points
across12paths reconcile to final cash. Strict TypeScript checking passes. This
is a source/data validation claim, not a rendered screenshot or MT5 chart check.

**Verdict: fix-then-ship. Research profit leader is the stronger historical
candidate for the owner's profit/DD objective; matching bot behavior and
independent broker/forward evidence remain the adoption blockers.**
