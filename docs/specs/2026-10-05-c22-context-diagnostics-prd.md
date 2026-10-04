# PRD: C22 causal context diagnostics before entry-filter research

## Problem Statement

The owner wants to improve the selected C22 + closed H4 EMA200 research strategy using ideas from support/resistance, daily volatility ranges and standardized distance from the mean. Today, indicator descriptions do not establish exact reproducible formulas, whether context adds useful information beyond C22, or how many winning trades an apparent improvement would remove.

C22's existing historical result is retrospective, cost assumptions remain inconclusive, and inspected history is exposed discovery data. A losing trade is not necessarily an implementation defect. Adding filters directly can change equity,10% cap admission and later trades, so removing losing rows from an old ledger cannot establish improvement.

The first deliverable is trustworthy diagnostics with unchanged baseline trading behavior. The owner explicitly confirmed public replay parity, causal-feature checks and CLI artifact/hash/resume tests before publication of this PRD.

## Solution

Provide an offline research workflow that replays frozen C22, attaches three precisely defined generic context features to completed-bar signals and executed trades, and produces a reproducible report with signal/rejection coverage and BUY/SELL outcome distributions.

The workflow must preserve the complete baseline ledger, equity path, risk admissions and lifecycle when diagnostics are enabled. It must identify missing context explicitly, retain winners and losers, and distinguish descriptive outcome analysis from counterfactual strategy performance. It produces evidence for a later filter campaign; it does not select or deploy a filter.

## User Stories

1. As a strategy owner, I want the frozen C22 contract identified in every run, so that results refer to the strategy I selected.
2. As a researcher, I want identical inputs and cost views for baseline and instrumented replay, so that differences cannot come from the environment.
3. As a researcher, I want unchanged baseline ledger and equity with diagnostics enabled, so that measurement does not alter trading.
4. As a researcher, I want each original signal identified by symbol, direction and completed-bar time, so that it remains traceable through macro and admission gates.
5. As a researcher, I want macro-blocked and unvisited signals distinguished from visited admission rejections, so that absent events do not look like absent opportunities.
6. As a researcher, I want rejection reasons retained, so that daily limits, risk caps and context are not confused.
7. As a researcher, I want actual admitted entry and initial stop from the authoritative ledger, so that normalized support/resistance room includes the original quote and rounding conventions.
8. As a researcher, I want unavailable entry geometry recorded as null with a reason, so that rejected signals do not receive invented executable prices.
9. As a researcher, I want completed-period support/resistance reference levels, so that future pivots cannot leak into earlier decisions.
10. As a researcher, I want daily-range features frozen from prior eligible days, so that the day's eventual range cannot influence its earlier signals.
11. As a researcher, I want standardized displacement based on completed closes, so that live-time and historical feature timing agree.
12. As a researcher, I want warmup, missing coverage and zero-variance cases explained, so that unavailable values are not silently treated as neutral.
13. As a researcher, I want BUY and SELL distributions shown separately, so that sparse BUY evidence does not get hidden by SELL volume.
14. As a researcher, I want winning, losing and flat outcomes retained, so that apparent loss avoidance includes its opportunity cost.
15. As a researcher, I want post-entry outcomes joined only after features are fixed, so that labels cannot enter feature construction.
16. As a researcher, I want missing-feature counts and denominators, so that a selective subset cannot masquerade as complete coverage.
17. As a researcher, I want frozen descriptive bins and sample counts, so that plots cannot choose their most flattering thresholds afterward.
18. As a strategy owner, I want net, drawdown, trade counts and risk-blocked events reconciled to baseline, so that the report remains grounded in actual replay outputs.
19. As an implementer, I want existing public replay and canonical geometry reused, so that a second trading engine does not diverge.
20. As an operator, I want artifact/source/input hashes, so that a result can be reproduced with the exact protocol.
21. As an operator, I want interrupted runs resumable only under matching hashes, so that stale cells cannot contaminate new results.
22. As a reviewer, I want a fresh full-result repeat and independent metric reconciliation, so that completion claims have evidence.
23. As an operator, I want bounded resource use and checkpoints, so that large tick histories remain manageable.
24. As a reviewer, I want descriptive diagnostics clearly separated from economic qualification, so that an interesting pattern is not called an edge.
25. As a strategy owner, I want unchanged Demo selection and risk protections, so that research cannot silently affect my Exness account.
26. As a reviewer, I want generic feature names distinguished from vendor implementations, so that the project does not claim unverified AlgoPrime parity.
27. As a researcher, I want already-inspected history labeled discovery data, so that it cannot be reused as an untouched holdout.
28. As a strategy owner, I want an explicit follow-up decision after diagnostics, so that any filtering catalog and economic thresholds are frozen before testing candidates.

## Implementation Decisions

- **Delivery boundary:** offline diagnostics only. No entry masking, new entry/exit rules, profit optimization, threshold search or account execution. TTS, GSS, proprietary vendor cloning and combined filters are deferred.
- **Baseline:** `variant_1af968e9ac6a26ea`, snapshot `RESEARCH-C22-H4EMA200-20261004`. Preserve fixed0.01, cost-inclusive10% cap, daily10%, one losing completed position per UTC exit day, single position, no recovery, existing BUY/SELL geometry and SELL protection. Preserve existing midnight accounting semantics; terminal availability and baseline recovery are separate work.
- **Replay reuse:** use the existing archived candidate detector, closed H4 publication timing, public tick replay, canonical entry geometry and optional admission-event capture. Prefer an offline annotator consuming these outputs. If insufficient event identity requires extending diagnostics capture, make it opt-in and observational; retain the default return contract and prove identical trading fields. Do not use the dedicated M5 entry-frame interface as a generic context hook.
- **Data:** use the exact archived continuous baseline inputs, raw results and manifest from the four-strategy comparison, with initial USD200 once per cost view and no seam resets. Verify original source/input hashes and full unrounded baseline results before annotation. Missing or mismatched artifacts are an explicit blocked input state, not a substitute-data success. Source instrumentation versions are recorded separately and compared against original baseline trading outputs.
- **Cost views:** retain all four existing base/stress and no-swap/current-spec-swap scenarios, including their TP fill conventions. These remain declared assumptions, not verified historical broker costs. Reuse the original protocols; no fee or swap retuning.
- **Timing:** aware UTC only. M15 features are available at bar close, never at bar open. Keep prior-period feature publication timestamps. Appending arbitrary future data must not change earlier values. Preserve existing H4 mapping rather than adding an unrelated extra shift.
- **Generic support/resistance proxy v1:** use high and low of the most recent fully covered, completed nonempty UTC trading day and of the immediately preceding fully covered completed UTC calendar week, Monday00:00 to Monday00:00. These are four Bid-derived reference levels, not vendor SRD zones. For an executed trade with direction d (+1 BUY, -1 SELL), entry E and initial stop S, retain levels L with d*(L-E)>0; choose the smallest positive distance and calculate room_in_initial_stop_units=d*(L-E)/abs(E-S). Use ledger E/S exactly, including modeled entry slippage and rounding. Do not reinterpret Bid levels as executable exit prices. Require coverage for both reference periods; otherwise status is unavailable. If coverage is valid but no level lies ahead, emit no_opposing_level with null numeric distance, not infinity or fabricated resistance. Rejected signals without a canonical admitted plan receive entry_geometry_unavailable; completed-period levels remain available independently.
- **Generic daily-range proxy v1:** at each UTC boundary, take the last20 fully covered completed nonempty UTC trading days before the current day; median of their high-minus-low ranges defines R, and the last eligible prior daily close defines anchor A. Publish these once for the current UTC day. For each completed signal bar close C, record signed displacement (C-A)/R and direction-adjusted displacement d*(C-A)/R. Prior-close plus/minus R are reference bounds only, not entry/exit instructions or the proprietary DZV formula. Fewer than20 eligible days or R<=0 yields unavailable. Current-day final high/low must never enter the estimator.
- **Generic standardized-displacement proxy v1:** arithmetic mean and population standard deviation (ddof0) of the last20 completed M15 closes including the signal bar; z=(C-mean)/sigma, plus d*z. Require20 valid closes; sigma0/nonfinite yields unavailable. This is an openly defined feature, not a reproduction of SD Mean and not a normal-distribution/reversal probability claim.
- **Coverage and gaps:** use input provenance to distinguish scheduled closures from missing market data. Do not fabricate candles or silently treat calendar completeness as trading-session completeness. Exclude partial archive-edge periods; retain explicit coverage status. If coverage cannot be established, dependent features are null while valid baseline replay may remain reportable. A new period becoming valid never retroactively changes earlier records.
- **Event schema:** versioned rows identify run, scenario, symbol, signal-bar close UTC, direction, feature availability/publication time, original/raw and post-macro direction where available, visitation status, canonical admission/rejection reason and optional ledger-trade identifier. Record actual entry timestamp and entry/stop geometry only when authoritative. Do not infer fictional missed trades or duplicate per-poll signals. Tie-breaking for duplicate levels is deterministic; decision availability and trade-entry time remain distinct.
- **Outcome separation:** realized net, exit reason, holding time and existing MAE/MFE are joined after immutable features are constructed. Rejected signals have no realized trade outcome. Feature values must never depend on win/loss, exit or future equity.
- **Descriptive reporting:** separate all-signal coverage, visited admission events and executed-trade statistics. Report BUY/SELL and cost view independently. Use fixed room bins <1, [1,2), >=2; direction-adjusted daily displacement bins <0, [0,1), >=1; direction-adjusted z bins <-2, [-2,0), [0,2), >=2, with unavailable/no-level categories separate. Boundaries are predeclared descriptions, not candidate thresholds. Include counts, wins/losses/flats and net totals/means; empty groups show null metrics. Preserve canonical win-rate units, profit factor and realized-RR null conventions. Do not rank bins as a strategy winner or claim statistical significance without an appropriate separately specified method.
- **Completeness and artifacts:** produce versioned protocol, input/source/transitive dependency hashes, diagnostics rows, canonical baseline result references, coverage summary, validation/repeat evidence and a synthesized review. Machine outputs belong under ignored campaign runs; only synthesized Markdown goes in reviews. Never overwrite original baseline evidence. Resume verifies every relevant protocol/source/input/artifact digest; mismatches block or start an explicitly new run.
- **Resource behavior:** reuse loaded read-only tick arrays and bounded processing; deterministic finite jobs, no indefinite tuning loops. Report runtime/memory observations without claiming unmeasured speed gains. Cleanup applies only to temporary outputs owned by the run.
- **Acceptance:** completion requires matching baseline trading outputs in every four-view scenario, causal/edge-case tests, complete record accounting with explicit missing statuses, fresh full-result repeat of substantive artifacts, independently recomputed baseline metrics and successful resume/mismatch checks. Operational timestamps may differ and must be isolated from deterministic comparison fields. Missing essential input or validation prevents COMPLETE. Correct diagnostics with insufficient usable samples may complete as evidence but must explicitly state INCONCLUSIVE_FOR_FILTER_SELECTION.
- **Future campaign boundary:** entry-filter implementation requires a separate preregistered finite catalog, exact economic gates, minimum sample rules, windows and ranking before candidate replay. It must replay the whole account path. Demo promotion requires a new strategy contract and separate operational review.

## Testing Decisions

- Test observable behavior through the public replay and campaign CLI, with small deterministic tapes where possible. Do not replace the detector, entry plan, ledger or account state machine with mocks that conceal timing/risk bugs. Mock expensive file acquisition only at input boundaries when needed.
- **Baseline parity seam:** run identical C22 fixtures with diagnostics disabled/enabled; compare all original ledger, equity, metrics and rejection-count fields exactly. Cover both directions, risk-cap rejection, daily loss count, existing midnight fail-closed behavior, SELL BE, BUY protection-off and final-sample close. Reconcile full archived baseline separately in the implementation acceptance run.
- **Causal feature seam:** use hand-computed fixtures through the annotator and public replay. Check future append/mutation invariance, completed-period publication, first eligible daily/week boundary, delayed first quote, weekend/session gaps, missing coverage, invalid timezone, NaNs, insufficient warmup and zero variance. Small unit tests may verify literal arithmetic, but cannot replace these public-path checks.
- **Geometry seam:** demonstrate that changing executable spread/slippage/grid changes entry-aware room according to canonical geometry while bar-only context remains the same. Test BUY/SELL side selection, no level ahead, duplicate levels, and unavailable geometry for rejected signals.
- **Event/label seam:** preserve raw/macro-blocked signal identities; distinguish unvisited, late, busy, circuit and risk rejection states from admitted trades. Every executed trade links once, with no fabricated outcome for a rejected signal. Alter future outcome labels and verify features unchanged.
- **Artifact/CLI seam:** execute a small complete run, interrupt/resume a controlled partial run, verify identical substantive results, corrupt/change each relevant input/source/protocol/artifact digest and require rejection. No COMPLETE marker on failure. Validate ignored output placement and preservation of baseline evidence.
- Existing prior art includes public breakout replay fixtures, directional entry/stop/cost regressions, archived candidate parity, source-pinned whole-catalog tests and CLI resume-source mismatch tests. Owner confirmed these seams before publication. Existing relevant suite ran67 tests successfully during review; these are not tests of the unimplemented diagnostics feature.

## Out of Scope

- Changing Demo runtime, starting/stopping watchers, sending orders, repairing MT5/Wine, resolving midnight account baseline policy, or enabling real money.
- New entry filters, signal generation, SL/TP/protection tuning, risk changes, recovery baskets or replacing C22 with TTS/GSS.
- Exact AlgoPrime reproduction, purchasing indicators, obtaining protected source, or claiming vendor equivalence.
- Choosing a winning filter, retrospective removal of losing trades as account-performance proof, broad parameter searches, inferential claims from sparse bins or guarantees of fewer losses.
- Calling inspected historical data an untouched holdout; multi-machine execution infrastructure or unrelated refactoring.

## Further Notes

The original proposal was scrutinized before this PRD. Findings addressed: undefined feature formulas, quote-aware geometry at the wrong stage, unspecified economic acceptance, and lost signal/rejection evidence. The owner selected the smaller diagnostics-first scope.

Context7 returned no AlgoPrime library. Its TradingView documentation supports causal implementation practice only. Vendor descriptions motivated hypotheses; they do not prove profitability. All previously inspected continuous history, including Jul–Sep2025, remains discovery data. A future forward-validation window must begin after its protocol/strategy is locked and use genuinely unseen observations.

Reference concepts: [AlgoPrime suite](https://algoprime.co/product/P00010/gss-and-tts-full-package), [DZV](https://algoprime.co/product/71d24f67-5b90-483e-b855-4f7330cf1b8d/daily-zone-volatility). Implementation timing references: [TradingView higher-timeframe data](https://www.tradingview.com/pine-script-docs/faq/other-data-and-timeframes/) and [lookahead bias](https://www.tradingview.com/pine-script-docs/concepts/strategies/).

Completion of this issue means validated diagnostic capability and a truthful evidence report, not qualification or deployment of a new trading strategy.
