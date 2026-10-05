# C22 context-filter proposal scrutiny

Scope: review the research proposal before synthesizing its PRD, not the entire working branch or Demo readiness. Intent: determine whether causal market context can improve C22 without mistaking retrospective selection for a verified trading edge.

## Simpler alternative

Build passive context diagnostics on the existing public replay output first. Do not implement five strategies or a new backtester. C22 already has trend filters; measuring added information is smaller and more informative than adding overlapping gates. A diagnostics deliverable can be accepted for correctness without claiming a profitable challenger.

## Major: feature names are not executable definitions

Finding: original proposal lines13-15 leave zone construction, daily-range estimator, rolling mean and standard deviation undefined.

Why: two agents could produce different signals under the same feature label; neither would establish parity with proprietary AlgoPrime tools.

Evidence: `docs/specs/2026-10-05-c22-context-filter-research.md:13` describes intended behavior but no calculation/confirmation/expiry contract. `scripts/research/reward156_search.py:154-234` supplies a fully specified archived baseline recipe, not vendor feature implementations.

Change: specify small, openly defined proxy features with versioned parameters and missing-data policies. Label them generic concepts. Vendor-exact reproduction remains outside scope without authorized formulas/source.

## Major: quote-aware room cannot be implemented as an OHLC-only gate

Finding: an executable-entry-to-level distance divided by actual initial stop distance is known at admission, not solely at signal-bar close.

Why: Bid/Ask, slippage, directional stops and grid rounding affect both numerator and denominator. A close-price approximation silently changes the intended feature.

Evidence: `scripts/research/breakout_entry.py:28-75` constructs adverse entry, rounded stop and target from quote/side/cost inputs. `scripts/research/breakout_replay.py:447-483` obtains the plan only after account gates and stores actual initial stop and entry. Optional `entry_frame` at `:37-43` is specifically an M5 interface, not an arbitrary context-frame hook.

Change: passive v1 uses authoritative ledger entry/initial-stop values for executed trades. For rejected signals without a canonical plan, normalized room remains null with reason; retain bar-based context separately. A later entry filter belongs after successful canonical plan construction and before position/fee mutation, with old account gates preserved.

## Major: success criteria mix software acceptance with strategy qualification

Finding: original line26 leaves minimum trades, windows and ranking open while promising an improvement comparison.

Why: post-result thresholds permit selecting a flattering outcome; a correct diagnostics tool can also legitimately find no useful filter.

Evidence: proposal `:26`; prior continuous report `docs/reviews/2026-10-04-four-strategy-continuous-backtest.md` reports only120/116 C22 base/stress swap trades, including21 BUY trades each. Directional subdivisions can be small. Existing `scripts/research/reward156_search.py:237` belongs to a different frozen qualification policy and should not be reused silently.

Change: v1 acceptance is exact replay parity, causal feature correctness, ledger reconciliation and reproducible diagnostics. No candidate selection or profitability verdict. A follow-up filtering campaign must freeze all numeric economic gates and finite catalog before running, then replay the complete account path. Report counts and uncertainty; no inferential strength invented from sparse bins.

## Major: erased signals lose rejection evidence and bias interpretation

Finding: zeroing direction upstream would hide context-rejected entries from existing rejection events.

Why: unexplained disappearance makes losing-trade removal appear beneficial while winner loss and changed future account admission remain invisible.

Evidence: `scripts/research/breakout_replay.py:135-163` emits visited admission/rejection events only with capture enabled; `:377-378` skips direction0; `:469-503` changes position and balance. `:204-219` updates daily losses and balance on exits, affecting later trades. The original proposal's entire-path replay requirement is necessary but not sufficient for signal observability.

Change: v1 records immutable original signal identity, macro-block state, visited event reason and ledger linkage without masking signals. Event trace is not a list of every possible strategy opportunity; distinguish unvisited/no-quote/macro-blocked bars. Hypothetical bins are descriptive, never a counterfactual equity curve.

## Trace and verification

Traced archived detector -> closed H4 macro filtering -> public tick replay -> existing admission guards -> canonical quote/grid/cost entry plan -> ledger/equity/daily loss mutation -> metrics and optional events. Consulted existing public replay/geometry fixtures, whole-catalog parity and CLI resume-source mismatch regression. No proposed context feature exists yet; no new feature behavior or profit improvement verified.

Verdict: **fix-then-ship the PRD**, by narrowing first delivery to causal diagnostics with exact generic feature definitions; no evidence yet justifies adding live entry filters.

Resolution: owner confirmed diagnostics-first seams. PRD specifies generic features, null policies, immutable signal/ledger linkage and artifact acceptance; entry filters and economic selection move to a separate preregistered campaign. Existing relevant regression executed: `.venv/bin/python -m unittest tests.test_reward156_search tests.test_reward156_tuning tests.test_breakout_logic tests.test_research_refactor_parity` ->67 tests in0.590s, OK. This validates existing seams only. **Revised verdict: ship the diagnostics PRD; feature implementation remains pending.**

Published via explicitly invoked to-prd skill: [GitHub issue9](https://github.com/Piti9427/XAUUSD_Scalper/issues/9), label `ready-for-agent`. Read back issue: OPEN, expected label present, published body matches local reviewed PRD. No strategy code or Demo runtime changed by this review/PRD task.
