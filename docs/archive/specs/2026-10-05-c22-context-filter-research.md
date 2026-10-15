# C22 context-filter research proposal

Status: research roadmap, revised after scrutiny. Owner confirmed **diagnostics first** on2026-10-05: public replay parity, causal features and CLI artifact/hash/resume tests; no entry filtering or Demo change in first delivery. The executable first-delivery scope and generic formulas are specified in [diagnostics PRD](2026-10-05-c22-context-diagnostics-prd.md). Broader hypotheses below are follow-up work, not authorization to tune or promote filters. No new backtest or profitability claim.

## Baseline and objective

Baseline is frozen `variant_1af968e9ac6a26ea`, `RESEARCH-C22-H4EMA200-20261004`, as CORE_STRATEGY section6.33. Preserve fixed0.01, cost-inclusive10% entry cap, daily10%, one losing completed position per UTC day, single position and existing direction-specific stops/targets/protection in initial experiments. No recovery.

Question: can an additional causal context feature reduce drawdown and losing entries without sacrificing net profitability or leaving too few trades? A losing trade alone is not a software defect. MT5/Wine availability and broker reconciliation are separate engineering problems; indicators do not solve them.

## Ranked hypotheses

1. **Support/resistance room (SRD concept):** measure distance from executable entry to nearest already-confirmed opposing level, normalized by initial stop distance. Hypothesis: insufficient room predicts failure before target. Risk: rejection can remove successful breakouts; an opposing level must actually lie ahead of entry, and may not be invented from future pivots. Requires explicit zone construction/confirmation/expiry rules before testing.
2. **Daily range position (DZV concept):** measure progress through an expected daily range derived entirely from data available at the fixed UTC daily boundary. Hypothesis: very extended entries have worse outcomes. Risk: strongest continuation days extend beyond expected range; do not assume exhaustion. Requires explicit estimator, lookback, anchor and missing-day policy; current day's eventual high/low prohibited.
3. **Standardized displacement (SD Mean concept):** record distance from a defined rolling mean divided by a defined rolling standard deviation, calculated on completed bars. Hypothesis: displacement helps distinguish late entries from continuation. Initially analyze BUY and SELL separately. Zero variance/warmup must be defined. This generic feature is not a reproduction of the proprietary SD Mean formula; touching2SD does not establish a reversal probability.
4. **Trend/structure (TTS concept):** lower priority because C22 already contains EMA50 direction/slope and closedH4EMA200. Determine incremental information before adding another trend gate. Any pivot/BOS/CHOCH implementation must specify confirmation time.
5. **GSS reversal:** separate challenger strategy first, rather than silently replacing C22 SELL breakout with a reversal. Combining both directions/regimes requires its own explicit contract and comparison.

## Evidence sequence

- Obtain available authorized vendor rules/source/settings, or explicitly name implementations as independently specified concepts. No claim of exact AlgoPrime parity from sales descriptions.
- First annotate baseline trades and eligible/rejected signals with causal features. Report winning trades removed alongside losing trades removed. This exploratory annotation cannot establish account-level improvement.
- Freeze a small parameter catalog and evaluation rules before new replay. Run baseline plus one filter at a time; combine only after an individual filter provides robust incremental evidence.
- Rerun the entire chronological account path for every variant: equity changes alter10% cap admission, daily limits and the later trade sequence. Do not subtract rejected losing trades from the old ledger to manufacture performance.
- Compare identical initial capital, original Bid/Ask ticks, base/stress cost views and swap assumptions. Report net, maximum equity DD, net per trade, profit factor, win rate, realized RR, trade counts, BUY/SELL breakdown, time exposure and risk-blocked intervals. Net per trade/PF/RR require explicit handling of zero-loss and zero-trade samples.
- Proposed acceptance: positive cost-inclusive net at least baseline and lower DD in the frozen comparison views, adequate participation, followed by forward evidence. Freeze exact minimum trades, window rules and selection/tie-break policy before execution; do not relax them after seeing results.
- Previously inspected full2024-09 through2026-10 history is exposed discovery data, including Jul–Sep2025. Chronological subdivisions of that history are robustness checks, not untouched holdout. Reserve genuinely unseen future data for forward validation.
- Keep research artifacts under `runs/<campaign>/`; publish synthesized verdict in `docs/reviews/`. Demo promotion is a separate decision and requires CORE_STRATEGY update plus broker/shadow gates.

## Sources and limits

Context7 lookup for AlgoPrime returned no library. Selected documentation library `/websites/tradingview_pine-script-docs` addresses implementation correctness, not trading edge.

- Vendor concepts: https://algoprime.co/product/P00010/gss-and-tts-full-package
- Daily zones: https://algoprime.co/product/71d24f67-5b90-483e-b855-4f7330cf1b8d/daily-zone-volatility
- Confirmed higher-timeframe data: https://www.tradingview.com/pine-script-docs/faq/other-data-and-timeframes
- Lookahead bias: https://www.tradingview.com/pine-script-docs/concepts/strategies
- Pivot visualization versus confirmation: https://www.tradingview.com/pine-script-docs/faq/visuals

Pine's confirmed higher-timeframe request example offsets the requested expression by one HTF bar with `barmerge.lookahead_on`; unoffset lookahead leaks future information. Do not mechanically apply an extra shift to C22's existing Python close-time mapping: preserve its defined publication timing. A pivot drawn backward on a chart is only actionable when the required right-hand bars have completed.
