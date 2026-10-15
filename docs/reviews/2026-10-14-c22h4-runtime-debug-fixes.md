# C22H4 runtime debug corrections — 2026-10-14

**Local fixes validated:** confirmed partial safety-close recovery, actual safety
cash/exit reporting, and read-only mode/readiness/blocker status. Owner retained
process-scoped daily baseline. No watcher restart, broker calls, cost attestation
renewal, native MT5 backtest or deployment was performed. Real money remains
PROHIBITED. Current default cost policy is still stale, so this correction does
not claim the running bot can admit new orders.

## Root cause and path

`cycle()` → `_reconcile()` treated every `safety_close_pending=True` as unresolved,
including a confirmed10010 partial close with a complete ledger and no pending
order. The persistent boolean survived restart and prevented residual recovery.
The full-close control worked. The independent cash-reporting defect constructed
`profit=net` and zero cost components instead of using the closing ledger.

`bot-status` inferred ability to send from the execution flag. The detector could
return WAIT before cost validation; this masked an expired attestation. Its poll
timestamp was labelled as a signal timestamp. Last-result overwrite also hid
prior blocked reasons; existing `trade_block_note` supplies a historical reason
without introducing a journal schema or per-bar outcome claim.

## Fix and compatibility

- `scripts/trial30/runner.py` adds persisted `safety_close_attempt`, original
  reason and owned ticket before send. Confirmed partial recovery requires
  positive closing progress, complete signed ledger/live volume agreement,
  requested-volume conservation, matching position identifier, fresh ownership
  and quote checks, and no pending orders. Retry volume is the actual residual;
  no lot rounding/top-up or new entry occurs.
- Timeout/placed/no-response and legacy boolean-only pending state remain
  UNKNOWN. Crash before response persistence therefore cannot cause blind retry.
  Definite rejected closes remain retryable. Safety halt stays after flatness.
- Complete closing ledgers feed both normal/safety result and atomic outbox
  event. Net summation retains `_cash` semantics. Immediate and late safety
  completions report actual gross/cost components and last exit deal; late
  completion keeps SAFETY_CLOSED instead of losing the safety cause.
- `scripts/ops/trial30_status.py` only reads local state/attestation. Execution
  mode, local readiness, expiry, heartbeat and historical blocker are separate.
  Fresh costs do not imply broker approval. Default and explicit policy paths
  are labelled; missing identity/policy fails local readiness. No renewal/write.
- Frozen strategy/risk/entry/BE settings, nine C22 source pins, JSON journal schema
  and process-scoped daily-baseline behavior remain unchanged. Additive attempt
  fields require no migration; old pending state stays conservative.

Fix pointer: current working-tree diff in the two modules above; no commit/PR was
created. Strategy declaration and operations notes were updated locally.

## Reproduction and falsification

Before production edits, existing invariant witness failed; new public-cycle
regressions ran8 tests with5 failures. pdb at original runner.py:661 observed
retcode10010/pendingTrue/live0.01/ledger0.01/no orders; at397→398 the next cycle
returned UNKNOWN without another request. Ledger completeness, pending orders and
restart metadata loss were disproved as causes of that witness. Cash breakpoint
showed net−1.60 with gross−1.00, commission−0.20, swap−0.30 and fee−0.10.

Negative controls now explicitly prevent retry when orders exist, history is
incomplete, residual volume grows, response remains ambiguous, or pending metadata
is legacy. Restart, BUY/SELL and foreign-position isolation are covered through
real C22 detector and public cycle with synthetic broker fixtures.

The earlier `probe.py` is an archived bug-witness that asserts pre-fix behavior;
it is not a post-fix acceptance command. The permanent regression suite replaces
that witness with completed-residual expectations and a broker fixture that can
acknowledge the follow-up close. No archived economic/source pins were rewritten.

## Requirement and evidence map

| Requirement | Exact regression evidence |
|---|---|
| Confirmed partial owned residual recovery | `test_confirmed_partial_close_recovers_only_owned_residual` |
| Recovery after restart without new entry | `test_restart_preserves_partial_close_evidence_without_new_entry` |
| Both sides and foreign-position isolation | `test_sell_partial_retry_uses_buy_close_on_owned_ticket`, `test_partial_retry_leaves_foreign_position_untouched` |
| No retry with pending order/incomplete or inconsistent ledger | `test_pending_order_and_incomplete_ledger_block_partial_retry`, `test_residual_volume_growth_blocks_partial_retry` |
| Ambiguous/legacy state conservative; definite rejection recoverable | `test_ambiguous_and_legacy_pending_never_blindly_resubmit`, `test_definitively_rejected_safety_close_retries_owned_position` |
| Actual immediate/late cash and exit price | `test_safety_close_reports_actual_cash_components_and_exit_deal`, `test_late_safety_completion_keeps_safety_kind_and_actual_costs` |
| Stale policy visible without signal; no attestation mutation | `test_expired_policy_is_visible_even_without_signal_and_is_not_refreshed` |
| Fresh costs do not qualify broker readiness | `test_fresh_local_policy_does_not_claim_broker_order_readiness` |
| Explicit missing policy, missing identity and shadow remain gated | `test_missing_explicit_policy_reports_source_and_blocks_readiness`, `test_missing_journal_identity_never_attests_cost_file`, `test_shadow_with_valid_costs_still_has_no_execution_readiness` |
| Owner: “คง policy เดิม แสดง blocker ให้ชัด” | `test_process_scoped_baseline_block_is_history_not_current_readiness`; `scripts/trial30/broker.py` unchanged |

Tests are in `tests/test_c22h4_safety_recovery.py` and
`tests/test_trial30_status_brief.py`. Assertions include side effects, persisted
pending state, request volume/count/ticket, no phantom FILLED event, safety halt,
outbox kind/components, and unchanged journal/attestation during status reads.

## Validation

- Final `make test`: **953 tests /85.085s/OK (skipped=2)**. All broker execution in
  this suite uses fixtures; manual MT5 smoke/native Tester was not run.
- `make compile deps lint`: PASS. Combined repository checks stopped at
  `format-check`:13 pre-existing files outside this patch need formatting.
  The four changed Python files pass Ruff lint/format checks. No aggregate
  `make check` success claim.
- C22 frozen source hashes:9/9 MATCH. Entry/risk/daily-policy source pins and
  config unchanged. Final scoped diff reviewed; no strategy retuning or fee/swap
  economic comparison.
- `make bot-status` observed fresh heartbeat/execution mode but BLOCKED local
  readiness due default cost expiry; historical blocker shown independently.
  Process inventory remains unavailable in the sandbox; local journal is not a
  direct broker exposure/history verification.
- Raw RED/green logs, debugger ledger and status capture:
  `runs/c22h4-runtime-scrutiny-2026-10-14/` (ignored). Existing test metadata/history
  preserved; owner edits/trade-note background output left intact.

## Why it slipped through and next action

Earlier fault tests simulated immediate full safety closure or checked only that
an unexpected fill was not advertised as FILLED. They did not cover confirmed
partial-close residual plus restart, or assert each closing cash component.
Status tests equated execution mode with ability to send. New regressions close
these gaps; broader architecture changes are not required for this correction.

Owner selected the original daily policy, so its multi-midnight admission block
is documented and remains reproducible rather than claimed fixed. Before runtime
rollout, review the concrete local diff, fresh owner cost attestation and required
broker/parity/shadow gates. A running watcher retains its imported code until an
approved restart. No deployment or automatic cost-policy timestamp refresh here.
