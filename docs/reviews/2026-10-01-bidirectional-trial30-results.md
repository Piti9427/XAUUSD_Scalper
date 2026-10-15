# Two-sided optimization against running trial30

**No verified replacement yet.** Three frozen catalogs completed288 distinct contracts, each all6 base/stress/full/half scenarios. Zero contracts met owner-confirmed gates. Existing trial30 Demo remains pinned; no rejected strategy was deployed and no forced order was submitted.

## Baseline correction

Original trial30 snapshot had not evaluated second_half. Replayed all windows on audited45,671,201 actual Bid/Ask ticks and12,100 canonical M15 bars,2026-03-28 through before2026-09-28 UTC. Same fixed200USD,0.01lot,10% cap, spread/cost model.

| Trial30 | Base net | Base DD | Stress net | Stress DD |
| --- | ---: | ---: | ---: | ---: |
| Full | $465.32 |26.01% |$361.40 |29.44% |
| First half |$346.54 |26.01% |$278.29 |29.44% |
| Second half, newly evaluated |$73.92 |32.93% |$12.17 |33.34% |

Trial30 itself exceeds30% DD in second_half. Original full-period results do not establish across-window qualification. Original daily log entries retained, correction appended separately.

## Search and measured failure

| Catalog | Contracts | Full-window passes | All-window passes |
| --- | ---: | ---: | ---: |
| D48 BUY quality + reward/protection |96 |0 |0 |
| Lower-wick/pullback BUY + D48 SELL |96 |0 |0 |
| Symmetric body/close-extreme/prior-day guards |96 |0 |0 |

Each requires actual BUY and SELL per scenario, >=60 full/20 half trades, net/WR/RR strictly above trial30, DD<=trial30 and<=30%, risk<=10%. Gates apply independently to both costs and every window. No skipped halves. Catalogs/source/input/protocol frozen before each round; independent forward/holdout qualification not claimed.

Diagnostic example, **not selected**: round2 trial46 lower-wick BUY/body/depth0.15ATR, D48 SELL, TP6.25ATR, BE1.5R. Fullbase +$538.72/DD28.61%/WR35.85%/RR2.4184; stress +$509.33/DD28.81%/WR35.85%/RR2.3729,9 BUY+97 SELL each. Profit/RR improved, but WR below trial30 and baseDD above trial30. Second-half DD38.44%/38.56%; only3 BUY. Cannot call this superior or deploy it.

Round3 trial15, **not selected**, passes only second_half: base+$404.01/DD20.44%/WR52.63%/RR1.3610, stress+$370.78/DD22.40%/WR52.63%/RR1.3214,26BUY+50SELL each. Fullbase+$446.23/DD34.01% and first_half+$180.77/DD34.01% fail net/DD screens; fullstressDD37.44%. Two round3 contracts pass second_half only, none full/firsthalf. This is regime sensitivity on already reused data, not permission to switch strategies using hindsight.

## Reproducibility and review

All original run directories retained locally: `data/strategy_bidirectional_trial30_campaign_2026_10_01`, `data/strategy_bidirectional_setups_trial30_campaign_2026_10_01` and `data/strategy_bidirectional_symmetric_trial30_campaign_2026_10_01`. Each contains protocol, source snapshots, audited input hashes, baseline and trial ledger/equity artifacts, completion hashes and verdict/progress. Current source changes reject old ordinary resume; frozen snapshots remain authoritative.

Fresh replay confirmation: **ALL_MATCH,1746 scenarios**, including three six-scenario baselines. Verification uses original hashed candidate-source snapshots, unchanged hashed replay/dependencies and re-audited raw inputs; compares entire six-scenario results including ledger/equity/all-tickDD, not just selected statistics. Repeated verification is not extra unique optimization contracts. [Tracked metrics/input/source/protocol/result hashes](2026-10-01-bidirectional-trial30-results.json). Audit commands `/tmp/verify_two_side_campaigns.py` and `/tmp/verify_two_side_round3.py`; observed logs `logs/bidirectional-trial30-verification.log` and `logs/bidirectional-trial30-round3-verification.log`. Local run artifacts remain full, tracked report retains selection metrics.

Standards: zero hard breaches/heuristics unresolved; original minor catalog duplication resolved with shared rules constructor. Spec: two original findings fixed—authoritative fresh replay on resume, and no frozen winner for incomplete catalog. Final re-review zero unresolved Spec findings. Separate axes; no broker execution by reviewers.

| Requirement | Test evidence |
| --- | --- |
| Each cost scenario improves net/WR/RR; risk/DD/fill counts enforced | `test_both_sides_and_each_cost_scenario_must_improve_trial30` |
| Both D48 directions execute fixed0.01 | `test_unfiltered_candidate_replay_executes_buy_and_sell_with_fixed_lot` |
| Lower-wick BUY plus breakout SELL execute | `test_lower_wick_buy_setup_and_sell_breakout_both_reach_replay` |
| Completed pullback BUY after EMA warmup | `test_trend_pullback_buy_reaches_replay_after_ema_warmup` |
| Causal BUY filter retains executable SELL | `test_buy_filter_keeps_sell_executable_and_future_bar_cannot_change_prefix` |
| Prior-day feature respects midnight bar close | `test_prior_day_filter_uses_completed_day_at_midnight_close` |
| Symmetric close-extreme25% thresholds admit both sides, reject inside edges | `test_symmetric_close_extreme_guard_accepts_both_edges_and_rejects_inside` |
| Resume rejects hash tampering and forged hashed metric; incomplete winner prohibited | `test_campaign_resume_rejects_changed_artifact_and_never_opens_broker` |

Final full suite746 tests:744 passed,2 skipped,12.133s. Focused52 campaign/replay/selection tests passed. Scoped mypy, repository Ruff, scoped format, compile and whitespace checks passed. Global format issue11 pre-existing files documented in prior implementation report remains outside scope.

## Demo and remaining work

Wine read-only probe08:04:34Z verified requested Demo/USD/equity200 and fresh latest tick. One transient `quote_stale` was observed and cleared without bypass or restart. Watcher08:05:08Z `execute=true`, WAIT/duplicate_bar, heartbeat0.70s, no active claim/halt/events. Latest completed08:00 bar had no SELL signal. No forward broker fill/BE proof yet.

Final watcher check08:14:07Z remains `execute=true`, WAIT/duplicate_bar, heartbeat0.46s, no active claim/halt/events. Current research work commits `8c55f32`, `70012f8`, `85f4505` on `feature/smc-v2-hardening`; final evidence commit follows. Review base develop, scoped implementation starts6e47f53.

Fresh broker reports `swap_long=-560`, `swap_mode=1`; BUY overnight swap is not included in this replay. Commission0 assumption, declared stress slippage, reused discovery and missing untouched/forward evidence remain limits. A future qualified BUY/SELL candidate needs cost-complete validation and runner parity before replacement. This work implements and verifies the research loop; requested superior runtime strategy remains unmet because no tested candidate passes. No background optimization continues after these finite catalogs/verification complete; Demo watcher continues independently.
