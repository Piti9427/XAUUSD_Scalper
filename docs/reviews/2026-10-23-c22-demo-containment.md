# C22 Demo containment correction — 2026-10-23

Local technical correction verified. Not deployed, no watcher restart, no real
broker mutations or external notifications. Fixed0.01, risk10%, daily10%, one
losing completed position/UTC day and frozen detector/source pins remain intact.
User Dobby research, existing trade notes and pre-existing CORE additions preserved.

## Technical evidence

- `make test-demo`: **126 tests, 68.232s, OK**.
- `make test`: **1,008 tests, 113.887s, OK (skipped=2)**.
- `make compile deps lint`: pass. Dependency check found no broken requirements.
- Changed Python files: Ruff format/check pass. Global format-check fails on15
  unchanged HEAD files, including frozen strategy/research pins; none reformatted.
- No static typechecker configured/installed; syntax compilation is not typechecking.
- Synthetic witness: `runs/c22-demo-containment-2026-10-23/probe-result.json`;
  append-only SQLite, notes, backup/restore and SHA256 manifest under its named
  `witness-*` directory. These are fixture results, **not Demo fills or profits**.
- Initial red tests, pdb trace, controls, review repros and final logs:
  `runs/c22-demo-containment-2026-10-23/`. `probe.py` creates a fresh timestamped
  witness on rerun. Full debug experiment ledger retained there.

| Requirement | Verification |
| --- | --- |
| Stable position identifier, comment collision containment, reticket | `test_comment_collision_cannot_replace_stable_identifier`, `test_ticket_change_preserves_identifier` |
| Post-fill finite SL/TP/volume/risk and non-widening protection | `test_post_fill_widened_stop_is_contained`, `test_stop_and_target_failure_matrix_after_fill`, `test_valid_tightening_and_be_survive_restart_then_never_widen`, `test_sub_tick_widening_cannot_ratchet_confirmed_stop` |
| Ambiguous ledger cannot mutate | `test_nan_opening_volume_never_mutates_or_confirms_protection`, `test_fresh_safety_ledger_mismatch_blocks_first_close` |
| UNKNOWN and confirmed residual-close recovery preserved | Existing `SafetyRecoveryTests`, including partial/restart, pending-order/incomplete-ledger, ambiguous/legacy and real cost components |
| Financial persistence blocks mutation; notes recover independently | `test_financial_persistence_failure_blocks_new_mutation`, `test_note_failure_does_not_escape_cycle_and_retries_after_restart`, `test_torn_note_outputs_recover_without_missing_body_or_duplicate_json` |
| Account switch immediately before mutation | `test_account_switch_at_final_mutation_gate_never_sends`; execution CLI requires dedicated terminal path |
| Shadow remains shadow under inherited gates | `test_make_shadow_targets_ignore_all_inherited_order_gate_values`; public C22/trial30 shadow tests assert no `order_send` |
| Baseline persists across restart/midnight and never relatches | `test_persisted_day_baseline_survives_restart_and_old_latch_is_blocked`, `test_missing_midnight_baseline_blocks_entry_but_manages_held_position` |
| v2 C22 168h, v1/trial30 24h, hashed cost/spec/swap evidence | `CostPolicyTests`: expiry boundaries, missing/changed evidence, broker spec drift, mandatory modeled swap and observed deal drift |
| Closed M1 validation before bootstrap/tail aggregation | `test_closed_m1_invalid_price_rejected_before_aggregation`; runtime wrapper used at both call sites, frozen bar assembly unchanged |
| Protection uncertainty/critical separate from process heartbeat | `test_unreconciled_protection_alert_at_180_seconds_not_hidden_by_heartbeat`, `test_fresh_journal_never_calls_existing_broker_exposure_flat`, `test_foreign_exposure_does_not_hide_behind_owned_position_protection` |
| Real HTTP success/429/503/timeout/lost acknowledgement | `DeliveryTests`; `test_real_http_retry_after_runner_restart_never_resends_order` combines real HTTP with public cycle and restart |
| Backlog/trickling HTTP cannot indefinitely block management | `test_delivery_backlog_is_bounded_and_health_coalesces_to_latest`, `test_trickling_http_cannot_extend_wall_deadline_or_spawn_unbounded_workers` |
| Append-only audit, seven complete backups, restore | `test_audit_is_append_only_and_report_preserves_real_net_costs`; SQLite UPDATE/DELETE rejected,8 backups retain7, restored audit count/checksum verified |
| Fixed-lot prospective/weekly evidence, containment impact | `test_weekly_window_separates_containment_net_from_lifetime`; read-only evidence CLI reports net USD, expectancy, PF, sampled equity DD, blockers, containment net and latency |
| Rollback compatibility | Existing trial30 lifecycle/CLI tests and deterministic `DemoRuntimeCompatibilityTests` |

Audit records UTC/event/correlation IDs, account fingerprint, release/config hash,
expected/observed state, request/response/reconcile and invalid numeric labels.
Financial transitions commit state/event atomically; API mutation remains a
separate non-atomic broker call. UNKNOWN never becomes a permission to resend.
Notes use completion footer, file/directory fsync and durable cursor. JSONL tail
repair affects derived notes only; authoritative financial history is retained.
Telegram delivery is at least once: lost acknowledgement may duplicate messages
with stable event ID, but never orders. Notifications/heartbeat have bounded work
and wall deadlines, one HTTP-only daemon worker/client and bounded response body.

## Standards review

Original findings resolved: fresh/finite ledger before first close, delivery
backlog and total HTTP deadline, durable note completion. Independent follow-up
reported **no remaining findings in targeted scope** and reran targeted tests.

## Spec review

Original findings resolved: NaN ledger mutation, fresh-journal/extra foreign
exposure protection, cumulative SL widening and missing weekly containment
breakdown. Independent follow-up reported **no remaining original Spec findings**.
These reviews do not establish exhaustive absence of defects or live readiness.

## Operational readiness and remaining gates

**Technical:** local offline correction verified; ARM/Wine/MT5 parity and dedicated
terminal behavior still require actual target-host validation. Templates under
`deploy/c22-demo/` are prepared, not installed or validated by systemd on Linux.

**Costs:** `COST_INCONCLUSIVE`. V2 evidence/document/calendar validation exists;
no live cost file or reviewed timestamp changed. Runtime lifetime168h applies to
C22 v2 only; cutover still requires <=24h attestation. No new economic comparison
ran. Baseline/latency comparisons must use base+swap and stress+swap; missing swap
metadata blocks that future campaign. V1 compatibility is not broker-cost proof.

**Profitability:** `INCONCLUSIVE`; real money `PROHIBITED`. Prospective grouping
uses release/config and actual fixed-lot cash ledgers; legacy unattributed trades
remain separate. Sampled equity DD is not continuous tick DD. Poll/blocker counts
are not independent missed signals. No normalized-R qualification, automatic
retuning or real-money activation introduced. 48h shadow/7 Demo days are
operational gates only.

**Oracle/cloud:** no OCI CLI/config or usable SSH target found locally. Actual
free entitlement and VM compatibility unverified. Timebox Box64/Wine/MT5/Windows
Python to one engineering day after access; on failure stop Oracle attempt and
use existing Windows fallback, with zero additional spend. No cloud resource,
bucket ACL, service installation or retention policy changed. Local backup
retains7 cumulative histories; remote7-snapshot retention and an actual private
bucket download/restore remain required before deployment approval.

**Shadow/cutover:** >=48h plus >=96 complete M15 bars across UTC midnight,
disconnect/restart/boot recovery, broker history/parity, fresh <=24h costs,
confirmed flat old sender/no trade that UTC day, clean journal/outbox and owner
approval at execution time remain pending. One account/one sender, no automatic
cross-host failover. Old watcher code is not reloaded by these file edits.

Postman API skills used for delivery contract/simulation. CLI1.73 mock server was
blocked by local `~/.postman` dataset permissions. Reusable mocks are retained but
not runtime-qualified; successful verification used real Python HTTP clients
against a loopback server. No remote owner-mock search/publication performed.
Contract references: [Telegram Bot API](https://core.telegram.org/bots/api#making-requests),
[Healthchecks ping API](https://healthchecks.io/docs/http_api/).
