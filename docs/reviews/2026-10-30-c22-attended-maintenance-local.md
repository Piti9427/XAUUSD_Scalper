# Selected26b8 attended maintenance local implementation

Status: LOCAL CORRECTIONS INDEPENDENTLY VERIFIED; 50FOCUSED/1565FULL PASS; NOT DEPLOYED.
The owner approved C-v2
for local source/tests. No VM,SDK,order,renewal,notification delivery,public write,
commit or financial-rule change accompanied implementation. Original23issue
scope remains16closed/7open:13,14,23,25,28,32,34.

Latest C-v2 checkpoint passes50focused tests and1,565standard-suite tests,
skipped2,exit0 in272.963seconds. All325application hashes stayed identical.
Independent post-fix review covers the seven reproduced defects and additional
PID/start-time,atomic-claim and destination controls. Evidence:
`runs/c22-attended-corrections-2026-10-30/validation-final.json` and
`runs/c22-attended-independent-review-2026-10-30/review-final.md`.
This is the completed C-v2 checkpoint; the later combined regression for newly
approved #23/H4 source is separate. Earlier39/1554and reviewer-quota text below
is retained historical evidence, superseded by this paragraph.

## Behavior and limits

Independent follow-up found seven concrete defects despite the earlier green
suite: real16-character identity versus64-character fixture,non-atomic terminal
receipt/account release,conditional recovery stuck after transient failure,
truthy UNKNOWN host flags,owned-probe omission after broker proof,late-reader
omission before manager start,and cleanup retry accepting a reused PID with a
different start identity. Original sources,witnesses and disproof controls are
sealed under `runs/c22-attended-independent-review-2026-10-30/`.

Those paths are now corrected. A real SelectedDemoRunner with a fake broker
establishes identity compatibility without rewriting the journal. Operational
completion and claim release commit atomically; terminal reinspection cleans
only a stranded same-operation claim. Conditional retries retain attempts and
require fresh safe-state proof; irreversible AP/cost/reboot work is not repeated.
Cleanup additionally binds the first exact operation/boot/PID/start/source
target before dispatch. Unknown flag types and noninteger position counts are
rejected. Reader/probe exclusion is rechecked after broker proof and before
start/final proof; live owned management is preserved on verification failure.

The current50focused tests pass and the independent reviewer repeated them plus
fresh same/changed/missing-target,atomic,unsafe-destination and legacy-claim
controls without finding another actionable local-path defect. This supersedes
the earlier independent-review quota limitation; it does not supersede the
documented absence of a production host adapter or prove any live broker fact.
The frozen-source C-v2 full suite passed1,565tests/skipped2. Previous39/1554
receipts remain retained as earlier validation. Later combined#23/H4 validation
is recorded separately and must not be inferred from this C-v2 checkpoint.

The deep module at `scripts/ops/attended_maintenance/` exposes prepare,run and
read-only inspect. Typed plans cover AP measurement,cost installation and reboot
through separate internal adapters. Source/config/unit/account/snapshot/cost/
review/backup and exact owner approval bind the operation. Its canonical0600
SQLite operation store is separate from the read-only financial journal.
Account claims survive controller restart; a local controller lock serializes
callers. Existing campaign controllers and source pins were not migrated.

STRICT_ZERO remains supported. Explicit OFF_NOTIFICATION_HANDOFF preserves every
original event id,raw payload and sent marker,including delivered rows; it never
deletes,marks sent,drains or sends notifications. Unknown schemas/kinds/cohorts,
unreviewed or unresolved CRITICAL events and uncertain delivery defer. New rows
before quiescence require another reviewed preparation; legitimate appends after
restoration require matching audit lineage. Ordinary bot admission is unchanged.

The module proves journal flat state before and after the hold,verifies actual
sender inactivity and absent readers before exclusive broker proof,and rechecks
freshness/context/budget after proof reads. It records effect intent before
dispatch. A timeout/crash never creates a replacement reboot or cost installation.
The same handle can continue when missing evidence is subsequently resolved.
Primary,cleanup and recovery errors retain separate stable stages and codes;
untrusted exception text is never copied into receipts.

AP cleanup binds operation,boot,PID/start and probe source. Cost recovery follows
the accepted generation marker and never guesses a coherent pair. Reboot waits
for changed boot/startup proof before restoration and labels manual fallback
separately from automatic retry. Missing outside-clock evidence produces
TIMING_UNVERIFIED; a numeric host UTC difference is insufficient. Pause/recovery
reserves are bounded by the approved maximum900seconds. Budget exhaustion stops
new work and retains permitted recovery; it does not abandon a live owned manager.

Original audit prefix and protected-key presence/raw values are checked alongside
every outbox row. An unproved day transition stays CONTINUITY_UNVERIFIED; no
midnight equity is invented. Verification failure after restoration preserves
the manager and actual later state. This module does not solve issue23's missing
genuine held-midnight proof method.

The production host adapter is intentionally absent in this authorized local
phase. Recording effects and disposable SQLite verify orchestration; they do not
prove actual VM identity,broker flatness,backup,AP repair,clock bounds,economic
parity or future profit. Actual VM use requires its own exact execution-time
approval and live source-bound proof. Old zero-outbox approvals are unchanged.

## Requirement and behavioral evidence

All named methods are in `tests/ops/test_attended_maintenance.py` and cross the
same public interface callers use. SQL assertions independently inspect real
temporary Journal rows; external effects use a recording host with no SDK/SSH.

| Requirement | Exact test evidence |
|---|---|
| “C: Typed plans + durable handle” | `test_controller_crash_during_hold_preserves_original_pause_origin`; `test_crash_during_action_cannot_become_unqualified_complete`; `test_durable_account_claim_rejects_another_operation_and_inspect_is_readonly` |
| “ครอบคลุมทั้ง 3 งาน คง adapter แยก” | `test_handoff_preserves_exact_rows_across_all_three_action_families` |
| “เก็บ id-payload-sent ครบและdelivery OFF” | `test_payload_change_with_same_count_is_detected_and_manager_preserved`; `test_row_delete_renumber_sent_and_schema_changes_are_rejected`; `test_delivery_enabled_or_uncertain_blocks_handoff_without_effects` |
| “CRITICALที่ยังไม่reviewหรือสถานะไม่ชัดยังdefer” | `test_unknown_notification_foreign_cohort_and_unreviewed_critical_defer`; `test_reviewed_critical_requires_exact_payload_and_resolved_condition` |
| “ไม่ลบ/mark sent/ส่งแจ้งเตือน” | `test_handoff_preserves_exact_rows_across_all_three_action_families`; `test_legitimate_append_after_restoration_preserves_every_prior_row` |
| Keep existing strict-zero scope | `test_strict_zero_defers_without_any_host_effect`; `test_empty_strict_zero_and_exact_effect_order_remain_supported` |
| Exact authority/source/account/snapshot/backup | `test_missing_wrong_or_drifted_approval_cannot_start_effect`; `test_freshness_source_backup_active_unknown_and_halt_block_before_hold`; `test_journal_account_and_snapshot_are_independently_bound` |
| One sender,quiescence,no SDK overlap | `test_stop_timeout_never_overlaps_broker_and_same_handle_resumes`; `test_lingering_reader_prevents_sdk_and_start_but_preserves_primary_failure`; `test_competing_sender_and_nonboolean_recovery_authority_are_refused` |
| Fresh exclusive broker evidence | `test_broker_foreign_exposure_stale_and_unknown_proofs_never_dispatch_action`; `test_slow_proof_read_revalidates_freshness_before_hold` |
| Separate AP cleanup/failure causes | `test_ap_primary_and_cleanup_failures_are_both_retained`; `test_foreign_probe_identity_cannot_be_signalled` |
| Coherent cost recovery without repeated install | `test_cost_accepted_marker_preserves_new_pair_after_lost_ack`; `test_cost_unknown_marker_cannot_restore_guessed_generation`; `test_cost_ack_without_acceptance_marker_cannot_report_success`; `test_resolved_evidence_continues_same_handle_without_repeating_cost_install` |
| No ambiguous reboot redispatch or false automatic recovery | `test_reboot_lost_ack_and_controller_restart_never_redispatch_or_preboot_start`; `test_automatic_reboot_recovery_is_not_labelled_manual_fallback` |
| Bounded pause and truthful crossboot time | `test_reserve_exhaustion_stops_work_and_recovers_review_without_action`; `test_missing_outside_clock_never_claims_crossboot_budget_pass`; `test_approval_expiry_prevents_new_action_without_preventing_approved_recovery` |
| Financial preservation and current owned manager | `test_original_audit_payload_tamper_is_detected_independently_of_outbox_count`; `test_held_midnight_protected_key_change_keeps_owned_manager_and_reports_unverified`; `test_running_owned_manager_after_hold_is_never_stopped_for_maintenance` |
| Private canonical store,no financial schema mutation | `test_operation_store_private_and_same_journal_serializes_controller_instances`; `test_operation_store_hardlink_to_financial_database_is_refused`; `test_financial_database_is_byte_identical_when_only_operation_is_prepared_and_inspected` |

## Verification and review

Initial public tests failed on the missing module. Subsequent root review found
two separately reproduced failures: a resolved-evidence handle could not resume,
and a slow proof read used stale pre-read time. Both were fixed and independently
asserted through the public interface. The latest focused command passes39tests:
`.venv/bin/python -m unittest tests.ops.test_attended_maintenance -v`.
Scoped Ruff and compileall pass. No static typechecker is configured or available;
coverage percentage was not measured.

First standard full suite ran1,551tests/275.918seconds:26failures,skipped2.
One context-campaign resume correctly rejected changing application-source pins
while implementation edits continued; isolated repeat after source freeze passed.
That campaign hashes every application Python file.25legacy webhook assertions
were affected by wall-clock rollover policy; a representative test reproduces
Rollover Flat Guard after20:55UTC even without importing this new module.
No legacy financial gate was removed or old fixture edited. Final standard run
against frozen sources passed1,554tests/284.041seconds,skipped2,exit0. All325
application source hashes remained identical before/after. The final run spanned
UTC midnight; legacy wall-clock-dependent fixtures can still fail after20:55.
The first failure and isolated disproof remain retained rather than hidden.

Standards review: root checked repository conventions,private artifact placement,
UTC,readonly journal access,exact row preservation and no dependency/public/VM
changes. Internal action adapters concentrate differing recovery knowledge;
plans expose no generic callbacks or command lists.

Spec review: root mapped the confirmed C-v2 contract to the methods above and
verified durable once-attempt behavior,strict-zero compatibility and continued
owned management. External host facts remain explicitly unverified. Parallel
reviewers hit usage limits; no independent final certification is claimed.

Machine receipts and retained failures:
`runs/c22-attended-maintenance-local-2026-10-30/`.
