# Daily-profit research with26b8 as the core

Verdict: feasible as a separate research hypothesis for higher average daily
profit and/or more intraday closes. No evidence yet that an added strategy raises
combined profit, and no claim of a profitable outcome every day. Current Demo,
native26b8, service, cost policy and financial journal remain unchanged.

## What the existing result actually says

Read the already verified native overlay-off fresh repeat, Base+modeled swap/raw,
initial$200, requested1Sep2024–24Oct2026 exclusive. No new economic replay.
All460 ledger nets sum to archived+$1,945.334 within1e-8. Existing DD34.2750% is
the archived full-tick result; this analysis does not recalculate it from daily data.

Assign each entire closed position's signed net, including lifetime swap/fees,
to its UTC exit date:329days with closes,123positive,205negative,1zero.
The783 requested calendar days include454with no closed position, weekends and
warmup. Those454days are NOT necessarily flat, no-trade or zero-equity-P/L days.
This accounting is not a daily broker cash-posting or marked-to-market return
series. Swap may have been charged on earlier holding days.

Changing attribution to Thailand calendar dates yields128positive/201negative
close days; these are the same trades and money, not an improved strategy.
The native risk day is UTC00:00→00:00, corresponding07:00Thailand→07:00Thailand.
Use that day for shared risk; separately display local calendar reporting.

Median holding time5.071hours,90th percentile26.032hours,maximum129.117hours;
290/460 trades open and close on the same UTC date.26b8 already has many intraday
positions, but it has no requirement to close or profit every day.

Source:
[daily analysis](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-daily-feasibility-2026-10-27/daily-analysis.json),
[original ledger repeat](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-risk-closure-2026-10-26/repeats/b996f43e0b7a5cae-base-raw.json.gz).

## Small bounded set of supplemental hypotheses

These are experiment definitions, not tested recommendations or new winners.

1. **Intraday trend pullback:** M5/M15 complete-bar retracement then confirmation
   in a higher-timeframe trend, with ATR-based invalidation and a preregistered
   session/time exit for the supplemental position. Existing26b8 unchanged.
   Main risk: correlated losses and short-horizon costs overwhelm the edge.
2. **Opening-range breakout:** build a range from a fixed count of completed
   bars after a dated session open, then confirm a breakout with volatility/cost
   filters. Handle DST explicitly; never use the eventual whole-session range.
   Main risk: false breakouts, news/slippage and hindsight-picked session windows.
3. **Range mean reversion:** only under a causal, preregistered range regime;
   enter a failed excursion/rejection and exit toward a mean, with a real stop.
   Main risk: an expanding trend defeats the range assumption. No averaging-down
   basket or martingale. Different setup names do not prove diversification.

No untested TP/SL/lot parameter is promoted. Start with a small fixed protocol,
not an open-ended indicator search chasing a daily-profit promise.

Older repository frequency campaigns show why more entries is not itself a
result: prior pullback/session cases lost under cost stress or exceededDD40%.
Those use different old comparator rules/windows and are cautionary context,
not a matched economic evaluation of core26b8 plus the hypotheses above.
[Prior economic verdict](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-10-15-native-frequency-economic-verdict.md).

## Shared account design and the core opportunity cost

Use one orchestrator, one sender, one account and a shared risk/loss ledger.
When flat, evaluate native26b8 first. Only if it has no eligible order may an
approved supplemental candidate be considered. Keep fixed0.01 and initial10%
cap, account-wide single exposure, daily budget/count/cooldown across BOTH
origins, identity/stops/margin/quote/UNKNOWN safeguards. Current ownership counters
are native-specific; a real combined implementation must deliberately aggregate
both strategies rather than granting each a separate full daily allowance.

A supplemental position may still be open when the next native signal arrives.
Prespecify arbitration; a simple initial study can keep the held position until
its own exit and log missed core signals. Do not silently force-close, queue a
stale signal or open a second position. Native signal logic can stay unchanged
while the actual executed native sequence changes. Therefore combined profit
cannot be calculated by adding two independent backtest nets.

If eliminating this interference is required, compare a different explicit
capital/exposure allocation as its own candidate. Two simultaneous bots on the
current account are not the solution under the existing single-sender contract.

## Evidence required before any Demo addition

- Same initial$200 and real Bid/Ask tape; same costs with swap in every scenario;
  mandatory base/stress/fee raw/cent, complete cash/volume/risk audits and full-tick
  combined equity/DD. No zero/missing-cost fallback.
- Compare native alone, each supplement alone, and each combined scheduler.
  Record missed native signals and marginal net after all costs.
- Overall net must improve against the matched core under the owner's selected
  profit/risk gates; worst tested combined DD must stay≤40%. Current native worst
  matched DD38.6710% already leaves only1.3290percentage points to that historical
  gate. This is not spare future risk capacity or a live DD guarantee.
- Measure daily equity changes at true UTC boundaries, not only closed-position
  nets: average/median, positive/negative-day ratio, worst day, loss streak,
  recovery, days with exposure/no closes and tail concentration. More winning
  days does not establish higher total profit or lower risk.
- Preregister parameters/sessions/ranking and account arbitration. Use genuinely
  unopened holdout if one exists; otherwise prospective forward collection after
  freeze. Reused discovery history and walk-forward partitions are not a new
  unopened market sample. Preserve all failed candidates.
- Independent validation and shadow→Demo review before adding any sender logic.
  No changes to running26b8 as part of this feasibility review.

## Skill discovery

Applied owner-invoked find-skills: checked leaderboard, searched CLI
`backtesting` and `quantitative trading`, inspected actual skill references and
GitHub sources. Recommended workflow candidate:

- [wshobson/agents@backtesting-frameworks](https://skills.sh/wshobson/agents/backtesting-frameworks),
 16.9K installs; [source repository](https://github.com/wshobson/agents)
 41.8K stars at27Oct2026 lookup. Community methodology, not performance evidence.
- [Actual SKILL.md](https://github.com/wshobson/agents/blob/main/plugins/quantitative-trading/skills/backtesting-frameworks/SKILL.md)
 covers bias, costs, OOS and walk-forward. Generic example code omits swap and has
 unsuitable intraday trade-count/annualization assumptions; use methodology and
 existing C22 tick engine, not blind code replacement.
- Optional install command: `npx skills add wshobson/agents@backtesting-frameworks`.
 No skill was installed. Skill popularity does not prove strategy profitability.

Methodology references: [Bailey et al., Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf),
[CFTC trading-system limits](https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/fraudadv_tradingsystem.html).
