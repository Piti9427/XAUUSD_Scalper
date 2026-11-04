# Selected26b8 local midnight timing correction

Status: OWNER APPROVED LOCAL FIX; INDEPENDENT49/FINAL1620 PASS; NOT DEPLOYED.
Original GitHub issue23 closed after exact owner approval at30October16:51:07UTC.
This corrects a reproducible loss of genuine
baseline evidence and an operator visibility gap. It does not recover an
unobserved midnight, widen the one-second window or qualify trading profit.

Storage recovered before the final rerun. Standard discovery passed1,620tests
in478.105seconds/skipped2,exit0; all327application and203test hashes remained
unchanged. Independent final review passed49focused/control tests and found no
remaining local implementation blocker. This supersedes the disk-blocked status
below without deleting or rewriting its failed receipts. The final evidence is
`runs/c22-local-combined-validation-2026-10-30/after-storage-recovery/` and
`runs/c22-midnight-final-review-2026-10-30/`. Local implementation closure can be
reviewed separately from a future approved VM rollout; neither has occurred yet.

Publication and local-scope closure have now occurred, with exact comment and
closed-state readback. A future approved VM rollout remains separate and has
not occurred. Receipt:
`runs/c22-closure-delivery-2026-10-30/approved-execution-receipt.json`.

## Mechanism and correction

The previous runner bracketed the whole identity wrapper, including terminal_info.
An account request at00:00:00.020UTC returned at00:00:00.040, but terminal validation
ended at00:00:01.140. The unchanged boundary predicate therefore rejected a genuine
first-second account observation. An isolated original-source witness reproduces
exactly that failure while six negative controls pass.

BrokerView now measures around the existing account_info call and retains its
original account object and aware UTC interval. Existing Demo identity, terminal,
permissions, capital and journal binding must pass before the runner attempts
capture. No additional SDK read or second reader was introduced. The boundary
predicate, first-proof immutability and financial arithmetic are unchanged.

Independent review then found a second gap: held management discarded the existing
baseline ValueError and a later mutation identity check cleared initial timing.
The supplemental cycle diagnostics now retain only the initial read timestamps
and the result of the existing baseline call. A slow held read reports
day_start_valid=False and day_start_reason=day_start_floating_unknown through the
public result and persistent last_result. Status remains MANAGING; original
protection, exit-day validity and admission decisions remain authoritative.
Diagnostics reset each cycle and never supply missing financial proof.

## Verified behavior

| Requirement | Exact regression |
|---|---|
| Preserve actual first-second response after slow terminal validation | `TimingRegressionControlTests.test_fast_account_slow_terminal_preserves_first_second_and_restart` |
| Reject slow, exact-one-second, missing/foreign/disconnected or invalid capital | `test_slow_account_remains_no_proof`; `test_account_return_at_exact_window_end_remains_no_proof`; negative controls in the same module |
| Continue held Selected management; genuine197USD proof survives later150USD equity and restart | `SelectedAccountTimingTests.test_held_selected_position_keeps_management_and_uses_only_genuine_restart_proof` |
| Preserve public/persistent reason and original interval, without new SDK calls or stale-cycle reuse | Additional assertions in that same held Selected test; `CandidatePersistenceTests.test_later_failed_identity_never_reuses_or_redates_prior_observation` |
| Preserve lifecycle exit-day validity | `CandidatePersistenceTests.test_exit_day_validity_is_not_relabelled_by_current_cycle_diagnostics` |
| Preserve missing-return semantics and remove old identity flags | `IdentityDiagnosticsTests.test_identity_diagnostics_are_reset_before_next_cycle` |
| Preserve exact injected/rollback cycle, state, orders and event parity | `DemoRuntimeCompatibilityTests.test_injected_strategy_matches_rollback_cycle_and_persistence`, with deterministic entropy and observation clock |

The76focused boundary/maintenance tests and eight independent-designed controls
repeated by root pass. The first combined standard suite ran1,615tests and found
two fixture assumptions: empty diagnostics after an account exception, and exact
comparison across independent unpinned clocks. Both failures reproduce separately.
Fixtures now assert current request/null return and absence of old identity/proof,
and compare both adapters with the same clock. Financial assertions were retained.
The expanded124focused tests pass in23.002seconds; compile, scoped Ruff and
whitespace checks pass. The final combined standard suite then stopped with
97errors/skipped2 after disk exhaustion (`No space left on device`), not a clean
pass. It reported1,613tests; this incomplete run must not replace the complete
1,615test denominator. All327application and203test source hashes stayed equal.
Increase available storage, then repeat the complete standard command. Original
fixture failures and the disk-failed rerun remain preserved. Current integration
qualification at that checkpoint was BLOCKED_ENVIRONMENT, not PASS. The later
storage-recovered1,620test pass above is the current integration result.

Initial independent review covered the timing patch, original RED and eight
additional controls, and discovered the visibility gap. Root then corrected
the diagnostic continuation and fixture alignment while reviewers were usage
limited. After review capacity recovered, a fresh independent final review
passed49tests against unchanged current source pins. That final review, rather
than the earlier root-only checkpoint, supports current local acceptance.

## Limits and remaining completion evidence

Slow or unavailable account reads, missing first-second scheduling, corrupt proof
and genuinely missed midnights still fail closed. Invalid baseline evidence does
not stop an otherwise valid owned manager; failure to persist required journal
state remains a different failure. Current account_info data is not a documented
atomic broker midnight snapshot. No current-equity reset or backdated mark is
permitted. Native rules, fixed0.01, cost-inclusive10%, daily10%/loss2 and cooldown
remain unchanged.

The VM was neither inspected nor deployed by this local change. Actual rollout
and broker observation require separately authorized execution and fresh proof.
No order, notification, renewal, GitHub write or commit occurred. This report
does not claim issue23 is closed or that a local test establishes profit.

Evidence: `runs/c22-midnight-frontier-2026-10-30/`,
`runs/c22-midnight-implementation-2026-10-30/`,
`runs/c22-midnight-independent-review-2026-10-30/`, and
`runs/c22-local-combined-validation-2026-10-30/`.
