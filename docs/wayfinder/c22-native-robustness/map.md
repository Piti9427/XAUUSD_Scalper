---
id: c22-native-robustness
title: Improve native 26b8 across market regimes at $200
labels: ["wayfinder:map"]
status: open
assignee: null
created: 2026-11-21
---

## Destination

Determine whether a candidate using the native 26b8 BUY and SELL signals improves net R per trade across market regimes and qualifies for an owner-reviewed Demo proposal under the [strategy robustness issue](https://github.com/Piti9427/XAUUSD_Scalper/issues/35).

## Notes

- On Mac or the research box, run matched native and candidate books from $200 at 0.01 lot under base+swap and stress+swap. Keep the cost-inclusive 10% cap with the next swap debit reserved, daily stop, and cooldown. The $400 weekly replay and $378.32 shadow snapshot supply diagnostic evidence. [C22 summary, 2026-11-21](../../../logs/trade-journal/C22_SUMMARY_2026-11-21.md)
- Use closed-bar data to define uptrend, downtrend, range, and volatility levels before measuring performance. Report BUY and SELL separately. Treat groups with fewer than 30 closes as diagnostic. Use 2023 to measure improvement and evaluate promotion against the existing qualification windows.
- Save each frozen protocol and its complete outputs under `runs/`. Compare realized monthly P&L, marked-equity drawdown, and admission differences using their own evidence. Include no-trade and zero-P&L months in the denominator.

## Research sequence

1. Reproduce native at $200 before ranking. Reconcile the ledger to net P&L and match signals to admissions or rejection reasons. Identify feed, spread, and cost-policy differences when comparing replay with Demo. Keep the account balance and price cutoff with each result.
2. Start with the native trades that contribute most profit after costs. Track retained TP trades, changes to their P&L, replacement trades, and cap-related rejections. Audit BUY and SELL separately across regimes. Keep a [record of weaknesses by round](strengths-and-weaknesses.md) and test a repair when the data show a mechanism observable at decision time. Freeze at most four variants per round and change one mechanism at a time. Alternative strategies may serve as diagnostic benchmarks.
3. Check the two issue periods, Nov 2022 to Nov 2024 and Nov 2024 to the frozen cutoff, plus Nov 2019 to Nov 2022. Use only prior data to choose each annual walk-forward rule for 2020–26. Validate shortlisted variants on Exness bid/ask ticks with matched cost assumptions. Record the 2023 effect alongside these checks.
4. In both primary periods and cost views require positive net, PF ≥1.2, DD ≤$200, worst realized month ≥−$100, and at least 60% profitable months. Require a positive annual walk-forward total. Rank qualifying variants by stress mean net R per trade, then lower DD and higher profitable-month share.
5. Run the qualifying candidate and native in matched prospective shadow for at least four weeks. Report closed P&L and open-position marks and check the linked BUY evidence decision. Publish findings in the strategy robustness issue. Open an implementation proposal only after the candidate beats native in shadow and meets the relevant evidence requirements. Demo changes require owner approval, a new release, and renewed review.

## Decisions so far

- [Require BUY shadow evidence for BUY changes](shadow-buy-evidence.md). A four-week shadow comparison needs evidence for the BUY behavior being proposed.

## Completed research

- [Round 14 — BUY reclaim and market regimes](../../reviews/2026-11-21-issue35-native-buy-reclaim.md). Reproduced the $200 native baseline, paired BUY and SELL results with D1 trend and H4 volatility, and evaluated four predeclared BUY entry filters. None qualified for prospective shadow.
- [Round 15 — Native BUY profit lock](../../reviews/2026-11-21-issue35-native-buy-profit-lock.md). Audited the +1R tick-to-M15 path and tested four late stop floors while retaining BUY TP3R. All four improved 2025 stress tick net and gave up net in the 2026 stress tick confirmation. None qualified.
- [2023 native loss diagnosis and research options](../../reviews/2026-11-21-issue35-native-2023-root-cause.md). Replayed the first loss streak, traced capital and risk-cap rejections, and matched cost differences and early-exit checkpoints. The owner can choose the next mechanism to investigate.
- [Rounds 16–17 — Walk-forward native BUY models](../../reviews/2026-11-21-issue35-native-buy-ml.md). Fitted six fixed policies using settled prior-year data. The simpler feature set increased coverage, while both direct loss prediction and net-R ranking left the stress holdout negative. No policy qualified.
- [Rounds 18–19 — Online 2023 repair](../../reviews/2026-11-21-issue35-2023-online-ml.md). Two versions of the 24-outcome directional gate made the independent 2023 book positive in both cost views, on M1 and Exness ticks. The exact 2023–August 2024 continuous book and both retrospective core-period screens still preclude promotion.
- [Rounds 20–21 — Non-overlap and guarded portfolio selection](../../reviews/2026-11-21-issue35-ml-portfolio-selection.md). The 12-month return selector kept 2023 positive and improved main-period terminal net and PF in both cost views on M1 and Exness ticks. Prior-period net and profitable months and main-period drawdown still fail qualification.
- [Rounds 22–24 — Drawdown and BUY-confidence gates](../../reviews/2026-11-21-issue35-ml-drawdown-confidence.md). The combined gate reduced main stress marked DD from $480.41 to $265.44 and improved net and PF. Prior continuous Exness net turned positive with only two green months, and full prior M1 still failed. The research goal remains active.
- [Round 25 — Admission and monthly activity](../../reviews/2026-11-21-issue35-ml-active-months.md). The account was already $232.78 below its peak before the SELL held at maximum stress drawdown. The SELL closed at TP. Adding minimum activity or green months to expert qualification made 2023 negative in every tested case.
- [Rounds 26–27 — BUY pause and recovery](../../reviews/2026-11-22-issue35-ml-buy-pause-and-reentry.md). A 48-hour pause after two severe BUY losses retained the 2023 repair and improved main-period stress net, PF and drawdown. Base drawdown increased relative to the combined control. Readmitting BUY from a faster improving settled-payoff estimate reversed the 2023 gain.
- [Rounds 28–29 — BUY structure exits and longer Exness coverage](../../reviews/2026-11-22-issue35-buy-structure-and-exact-coverage.md). The early BUY exits preserved some cash on initial stops and also cut profitable recoveries. The verified archives now cover the earlier core dates and extend the main tick replay to 17 November 2026 Bangkok time. The strict combined profile was profitable in both tick periods and both costs, with only 2/25 green months in the earlier period and excessive main marked DD.
- [Rounds 30–33 — Monthly opportunity audit and $200 budgets](../../reviews/2026-11-22-issue35-monthly-opportunities-and-budget.md). Native has individually realizable winners in 23/25 prior months under both costs. The supported $40 monthly boundary with 0.5R range protection has 15/25 green months in prior exact stress and passes the main exact screens. Prior exact stress still fails net and PF, and M1 fails both-period qualification.
- [Rounds 34–38 — Stop fallback under the account and month limits](../../reviews/2026-11-22-issue35-cap-fallback-and-stability.md). The 2.0ATR stop used only when the 2.5ATR plan fails an existing risk budget passed both core Exness screens, including 17/25 and 16/25 profitable months in prior and main stress. Independently reset 2023 and annual selection on Exness remain negative in stress. Prior M1 remains negative.
- [Rounds 39–42 — Range BUY losses, latest broker replay and shadow freeze](../../reviews/2026-11-22-issue35-range-buy-shadow-registration.md). The $20 realized monthly range BUY boundary kept both core Exness windows qualified and turned independently reset 2023 positive in both costs. Expanded-pool selection on two or three preceding years was also positive on Exness and negative on M1. The local research shadow is frozen and registered to begin 23 November 2026 Bangkok time.
- [Round 43 — Cross-feed attribution](../../reviews/2026-11-22-issue35-cross-feed-attribution.md). Substituting M1 signals on common bars reversed prior stress profitability while retaining Exness ATR, execution and cost assumptions. The paired replay traced the first divergence through the EMA50 extension gate, position occupancy and monthly risk headroom.
- [Round 44 — Matched BUY evidence audit](../../reviews/2026-11-22-issue35-shadow-buy-evidence-audit.md). The read-only report matches decision bars and ledger outcomes. It verified a historical range BUY pause against the pre-pause comparator and preserved the native comparison separately.
- [Round 45 — Continuous 2019–22 Exness check](../../reviews/2026-11-22-issue35-exness-2019-2022.md). Newly verified 2019 Bid/Ask archives allow one continuous book from November 2019. Range20 stayed positive in both costs with markedly less drawdown than native, while PF remained below 1.2 in both costs.
- [Round 46 — Historical context for the 28-day shadow](../../reviews/2026-11-22-issue35-shadow-window-context.md). In the main period, range20 reduced marked drawdown in both costs in 22 of 25 windows and beat native on terminal net in both costs in six windows. The range BUY pause never fired in the 51 historical windows that started with fresh capital.
- [Round 47 — Continuous $200 Exness replay](../../reviews/2026-11-22-issue35-continuous-exness-2019-2026.md). In a single continuous book across 2019–26, range20 stayed profitable in both costs. Native reached the main period with about $17 and the same 10% cap rejected every signal in both costs.
- [Round 48 — Trade from realized gains above the monthly target](../../reviews/2026-11-22-issue35-monthly-gain-buffer.md). The trend SELL option added four main-period trades while preserving the earlier ledger, monthly green counts and marked drawdown. Admitting BUY as well raised main stress drawdown above $200.
- [Round 49 — Validate the trend SELL option across years](../../reviews/2026-11-22-issue35-monthly-gain-buffer.md). The option retained the independently reset 2023 result and added one winner in continuous 2019–22. The prior-years-only selector made the same selections after including it in the pool.
- [Round 50 — Rehearse shadow archive refresh](../../reviews/2026-11-22-issue35-shadow-refresh-rehearsal.md). The pinned poller accepted a growing archive across two months, preserved all prior closed outcomes and rejected a shortened archive. The completed historical fixture still lacked BUY evidence.
- [Round 51 — Reconcile the archived Demo sample](../../reviews/2026-11-22-issue35-demo-native-reconciliation.md). The same-time replay matched three Demo slots. Two unmatched Demo entries failed the $200 replay cap, and the first differed at the 48-bar breakout boundary on the public feed.
- [Round 52 — Entry-latency sensitivity](../../reviews/2026-11-22-issue35-entry-latency-sensitivity.md). Range20 kept both core periods above the historical gates under 15-, 30- and 60-second fill delays, with meaningful differences in P&L by cost view.
- [Round 53 — Long swap sensitivity](../../reviews/2026-11-22-issue35-swap-rate-sensitivity.md). Range20 passed both historical windows at the three rates tested. The cheaper main base case admitted an additional loss near the monthly risk limit and changed later admissions.
- [Round 54 — Joint entry-latency and long-swap sensitivity](../../reviews/2026-11-22-issue35-latency-and-swap.md). Range20 retained all core historical gates at a 60-second delay and −644.8 POINTS long swap. The combined main base case changed January admissions through the monthly risk limit.
- [Round 55 — Paired monthly robustness evidence](../../reviews/2026-11-22-issue35-paired-monthly-evidence.md). Range20 made far more months profitable in the older window. Native led on profitable months and median realized monthly net in the main window, where range20 reduced the depth of drawdown.

- [Rounds 56–57 — Feed-noise margins on range-leg thresholds](../../../runs/issue35-feed-margin-band-2026-11-23/STAGE-A-RESULTS.md). Margins were sized from the measured Exness–M1 indicator noise rather than from P&L. The pooled margin improved prior M1-signal stress (−85.15 to −48.07 at d75) but failed no-regression through path effects. The derived per-feature band margins b75 and f75 passed prior Stage A in both costs but fell below range20 in the main window in both costs. There, the directly filtered range trades were net winners. Neither qualified, and the margin family is closed.

- [Round 58 — Read-only design screen](../../../runs/issue35-round58-design-2026-11-23/SCREEN.md). The panel screened a range-leg regime exit, a re-signal stop tightening and the range-route stop fallback. Each one's pass rests on one to four trades that have already been seen, and outcomes were exposed before the freeze. No round-58 replay was run. On 2026-11-23 the owner concluded the tuning goal: no new variant qualifies, Demo stays on native, and the registered range20 shadow continues.

- [Rounds 56–58 summary and tuning conclusion](../../reviews/2026-11-23-issue35-feed-margin-and-tuning-conclusion.md). This summarizes the feed-margin rounds, the round-58 screen, and the owner's decision to keep native while the range20 shadow continues.

## Next research check

- Observe the frozen range20 and native books from 23 November 2026 under identical prospective bid/ask and account assumptions. Report at least four weeks and resolved BUY evidence. Keep the M1 cost and feed discrepancy in scope as a robustness check for any later proposal. [Shadow rules](../../../runs/issue35-range20-prospective-2026-11-22/protocol.md)

## Out of scope

- Real-money orders and replacement signals for an eligible candidate.
