# Selected26b8 operability fixes and remaining issue closure

Owner: “ดำเนินการ fix”, then “continue”. Local implementation and immutable
release staged; **not deployed**. Native Rules26b8bcd69e043653 and economic
selection remain. This closes bounded operational defects, not all19 issues or
the native MT5 optimizer trigger. No new economic backtest or broker order.

## Changes and evidence

The smallest change is to retain the existing sender, admission and protection
paths and improve the existing observer/status seams. No new risk engine,
broker reader, recovery sender, notification channel or monitoring stack.

1. Watchdog retains an incident across transient healthy polls and rotating
   blockers, including observer process restarts. It clears only after a
   continuous issue-free interval equal to existing problem_grace_seconds
   (default180). Announced incidents remain critical during RECOVERING. Existing
   urgent incidents and outbox retry/deduplication remain. Invalid/future/out-of-
   order observer timestamps produce watchdog_state_invalid and finite sanitized
   findings rather than a silent wait or reflected private payload.
2. A flat stale quote no longer proves market closure. Quote age over the
   existing stale threshold or continuous wait reaching the grace reports
   market_data_wait_session_unverified. An initial short wait remains. Missing
   age cannot wait indefinitely. This is conservative session uncertainty, not
   independently attested session-aware market-open detection.
3. ExecutionReview.inspect shares the original validator but never accepts or
   writes approval. It exposes finite failures and policy expiry/due72/24/6h,
   even when earlier identity/quote gates prevent admission. Source/account/
   policy binding and original selected_execution_review_invalid error stay.
   Bound approval/arm UTC times appear only after successful validation.
4. Cycle entry_availability reports known blockers, observation time, operator
   action, conditional resume and exact known cooldown/day/arm/new-bar times.
   Prior timestamps are validated. KNOWN_BLOCKERS_ONLY and NOT_PROVEN explicitly
   limit coverage. These read-only observations happen after existing financial
   operations; inspection failure cannot replace a protected owned result.
5. Previously prepared whitelisted identity diagnostics are included in the
   staged release: same SDK reads, no repeated optional getter and no permission
   bypass. They explain a connection failure; they do not repair native AP choice.

Existing compatibility entry_ready remains unchanged. New availability fields
separate liveness, protection and new-entry conditions. No automatic cost renewal,
review timestamp rewrite, halt clearing, financial baseline reset or order retry.

## All19 issue dispositions

1. **AP reconnect — OPEN.** Native logs establish the handoff mechanism; deeper
   optimizer trigger unproved. Latest read-only VM capture27Oct12:48:52Thailand:
   original release active, samePIDs, no restart, latest permission block. An
   absent owned journal intent with observed_positions=null is not broker flatness.
2. **Generic permission cause — LOCAL FIX READY.** Same-read diagnostics tested
   in the earlier root-cause task, bundled here, not yet visible on the old VM.
3. **Policy expiry — PARTIAL.** Countdown/due/review-cause visibility fixed.
   Current1Nov20:25:18Thailand expiry remains; new genuine evidence and coherent
   source/policy review are still required. Standing automatic renewal not granted.
4. **Hidden blockers — LOCAL FIX.** Known independent review/halt conditions and
   current gate result now visible together. Unreached checks remain unproved.
5. **Watchdog flap — LOCAL FIX.** Persistent incident/stable recovery tested.
6. **Unbounded stale-feed wait — LOCAL FIX.** Bounded unverified-session incident;
   exact dated account-specific session evidence remains OPEN.
7. **Held-midnight1s proof — OPEN.** Existing financial proof policy unchanged;
   visible operator/resume reason added. No invented historical equity.
8. **UNKNOWN resolved but halt latched — EXPECTED GUARD.** Resolution action is
   explicit; automatic clearing remains prohibited without incident review.
9. **External notification/VM death — OWNER DEFERRED.** Delivery stays OFF and
   is labelled; no external observer/channel or paid infrastructure installed.
10. **Repeated H4 incompleteness — RESEARCH REQUIRED.** Native strict16/16 remains.
    Last observed11:00Thailand recovery occurred without restart. Carry/session
    changes need a distinct candidate with matched swap-inclusive replay.
11. **Live DD40 budget — RESEARCH ONLY.** Runtime has no DD40 breaker; prior risk
    study did not select a better replacement. Historical DD is not enforcement.
12. **Prospective dailySL budget — RESEARCH ONLY.** Native observed10% stays;
    testedD1 worsened worstDD to40.7161%, so not silently promoted.
13. **Swap-inclusive Net BE — RESEARCH ALTERNATIVE.** B1 reduced baseprofit11.45%
    for lowerDD; no maximum-profit replacement selected.
14. **Streak/recovery downside — OPEN TRADE-OFF.** No tested replacement preserves
    all matched native profit and strictly improves the measured downside.
15. **Daily-profit addon — NOT IMPLEMENTED.** Requires joint account/risk replay;
    daily profit is not guaranteed by changing trade frequency.
16. **Compounding lot — OWNER PAUSED/NOT IMPLEMENTED.** Fixed0.01 remains.
17. **Actual cost parity — EXTERNAL EVIDENCE MISSING.** COST_INCONCLUSIVE and
    Swap-Free UNKNOWN retained. No cost attestation fabricated.
18. **Fresh holdout/production parity — OPEN.** Existing exposed-history returns
    do not include this VM's AP outage/policy housekeeping. No new holdout claim.
19. **Native forward lifecycle/actual reboot — NOT VERIFIED.** Manual smoke and
    unit tests do not establish full native signal→fill→BE→close or reboot success.

## Reproducibility and verification

All machine artifacts are under
`runs/c22-operability-fix-2026-10-27/`. Original root-cause artifacts preserved.
RED watchdog/availability logs precede fixes. Independent review found malformed
types, future/inconsistent timestamps and reflected prior times; each has a
permanent failing-then-passing public regression. Last bounded re-review PASS.

Exact requirement mapping:

| Requirement | Evidence |
| --- | --- |
| Intermittent blocks/restart cannot erase incident | `test_alternating_permission_failure_survives_healthy_samples_and_restart`; `test_changing_blockers_does_not_reset_incident_or_duplicate_alert` |
| Stable recovery, exact boundary and once-only notification | `test_recovery_requires_continuous_grace_and_emits_once_at_exact_boundary` |
| Old/missing quote age cannot silently wait forever | `test_day_old_quote_is_explicitly_unverified_session_not_market_closed_proof`; `test_missing_quote_age_wait_is_bounded_across_observer_restart` |
| Observer state cannot fabricate recovery or leak data | `test_future_or_invalid_persisted_times_raise_local_incident_instead_of_waiting`; `test_recovery_before_incident_start_cannot_clear_an_announced_incident`; `test_invalid_protection_type_stays_unknown_without_crashing_observer` |
| Review inspection cannot authorize or renew | `test_armed_inspection_never_persists_acceptance_but_check_still_does`; `test_exact_expiry_preserves_gate_and_due_thresholds_without_renewal` |
| Hidden expiry visible behind connection failure | `test_upstream_connection_block_still_reports_actual_expired_review_without_acceptance` |
| Owned BE continues through missing review/inspection failure | `test_revoked_review_does_not_stop_owned_protection_or_repeat_entry` |
| Resume is conditional, downstream checks unproved | `test_cooldown_and_daily_resume_expose_conditional_boundaries_without_reset`; `test_armed_time_and_new_bar_waits_have_bound_conditional_resume_without_operator` |
| No extra broker read or financial journal mutation | `test_public_cycle_reports_flags_halt_and_unreached_checks_without_extra_sdk_reads`; all continuity `sample()` checks journalSHA unchanged |
| External delivery OFF remains explicit | `test_disabled_delivery_still_records_durable_local_incident`; existing CLI opt-in regression |

The review agent compared original/new admission outcomes and journal writes on
40strict/armed/restart/malformed/binding/cost/time cases: exact parityPASS. Frozen
101 source pins match; native config is identical except mutable execution.py
source binding. No configured coverage percentage/typechecker result is claimed.
Final full-suite and package integrity results are recorded below after completion.

## Skills and deployment boundary

find-skills leaderboard and CLI search performed. Original npm cache was
unwritable; a temporary cache avoided changing its ownership. Candidate
[monitoring-expert](https://skills.sh/jeffallan/claude-skills/monitoring-expert)
directory showed5.6K installs/12K repository stars, but no new skill, dependency
or monitoring infrastructure was necessary or installed. Existing debugging,
testing and outsider-review workflow used directly.

Immutable archive and units are staged as `selected-3916d35b2d095b1a`, execution
authorizationfalse in the package. VM cutover is separate: existing runtime
source/config approval cannot silently bind different bytes. Preserve journal,
policy age/evidence, one sender and owned management; prove flat/noUNKNOWN,
review exact new cohort and validate after activation. Terminal/AP experimental
configuration is not part of this patch. Full AP-trigger resolution remains OPEN.

## Final validation and VM distinction

- Focused63tests/24.114sPASS. Full unittest discover:1312tests/195.242s,
  OK(skipped2),exit0. There are33new permanent tests in this task. Existing
  dry-run/negative CLI fixture messages in the log are not actual broker orders.
- ScopedRuff,py_compile and git diff --checkPASS; source verification returns
  CONFIG_SOURCES_VERIFIED/broker_api_calledfalse. No dependency change.
- Independent final reviewPASS after all five reproduced robustness findings
  were closed. Review validator original/new40-case outcomes and writes match.
- Staged archive verifies80files,71Python syntax compilations and19selected
  source hashes; no credentials,env,financialDB or run output. ArchiveSHA256
  691e957987f4e9a7e71341b91b98d384249cf77a9b6daabdd0429b947285a567.
- Final VM read-only capture27Oct12:58:59Thailand confirms original release
  selected-9cfc54a3dc78f0ae, same sender/terminalPIDs andNRestarts0. Latest
  observed positions remain unknown during algo_permissions_required.
  Cost-policySHA247cf2a51d96beb5c805aba2daba9e9c45d49cbff5645514e76811c5fd1babd0
  unchanged. No VM source,unit,policy,journal or broker state mutation.
- Exact task delta, preservation, validation, archive verification, immutable
  before snapshots, RED/GREEN logs and read-only capture are retained in the
  ignored run directory. No commit or deployment claimed.
