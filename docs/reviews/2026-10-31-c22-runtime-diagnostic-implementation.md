# Selected26b8 runtime SQLite diagnostic implementation

Status: exact owner-approved standalone patch002c is applied locally. Focused
regression, lint and the corrected standard full suite pass. The final run has
1,630 tests, two skips, exit0 and all531 scripts/tests hashes unchanged. The first
full run's two fixture failures remain preserved. No VM rollout,
source rebinding, financial-rule change or repair of the unknown live SQLite
trigger is claimed.

## Reproduce and trace

The retained deployed runtime failed at `Journal.put` connection-context exit.
Its diagnostic retained the Python OperationalError and source frames but omitted
available native SQLite code/name. A deterministic in-memory fixture reproduces
that diagnostic omission. The prior constructor/resource proposal4465 does not
cover plain runtime errors and remains separate/unapplied.

The owner approved standalone patch SHA256
`002c3132369dd7c80ad8de522602e0ebac2fc5a7398c8c1f413edec2affaa3b4`.
The resulting `scripts/demo_runtime/diagnostics.py` SHA256 is
`162f597f97a0680f04b60f6a5327ee5fd86ad72aeacde70f4e4b0d16da267603`.
Only validated SQLite numeric code, matching native name and primary code are
added to runtime/fallback diagnostic details. Unknown/malformed values remain
null/UNKNOWN. Original exception identity/cause/traceback, SQL, transactions,
retry behavior, risk/order callers and non-SQLite envelope remain unchanged.

No debugger was attached to a live financial process. Local tests use in-memory
SQLite, synthetic state and a mocked broker boundary. They exercise canonical
Journal, selected/shared runner and CLI paths without broker access.

## Falsification and applied-code evidence

The ten portable canonical tests fail against the exact old diagnostic module
loaded only in memory; the current file remains unchanged during this RED control.
The same tests pass against the approved applied module. Thirty-four focused
tests pass with ResourceWarning treated as an error; Ruff and in-memory compile
checks pass. The proposal's earlier14+3 controls are retained separately and are
not substituted for applied-code results.

| Requirement | Exact canonical test |
| --- | --- |
| Available native fields; unchanged public envelope and original exception | `RuntimeSqliteDiagnosticsTests.test_runtime_native_codes_preserve_public_envelope_and_exception_identity` |
| Actual engine-generated errors, including extended constraint code | `test_actual_sqlite_errors_retain_native_extended_codes` |
| Honest missing/invalid/faulting metadata; no forged secret-bearing names | `test_missing_malformed_and_unknown_native_metadata_stays_honest`; `test_mismatched_names_and_external_details_cannot_forge_native_fields`; `test_faulting_native_properties_cannot_mask_the_original_error` |
| Non-SQLite and known gate behavior unchanged | `test_non_sqlite_fault_and_known_gate_keep_existing_details_and_classification` |
| Fallback retains safe persistence facts without record mutation | `test_fallback_adds_safe_persistence_fields_without_mutating_record_or_recursing` |
| Context-exit failure keeps rollback, cause and original put origin | `test_actual_journal_context_exit_keeps_exception_cause_and_rollback` |
| Actual canonical CLI exits/shuts down once and sends no order | `test_current_cycle_to_real_cli_keeps_exit_shutdown_and_no_order` |
| Export returned before optional subsequent put failure | `test_post_export_put_failure_keeps_optional_path_and_native_evidence` |

New tests live in `tests/demo/test_c22_runtime_sqlite_diagnostics.py` and import
canonical code only. They do not rely on ignored runs, candidate source copies or
private deployed-source fixtures.

## First full run and narrow fixture correction

The first full command was `.venv/bin/python -B -m unittest discover -s tests`.
It ran1,630tests with two failures and two skips in274.030seconds. All531 source
and test hashes stayed unchanged throughout. Both failures are subcases of
`SelectedAccountTimingTests.test_held_selected_position_keeps_management_and_uses_only_genuine_restart_proof`.
They are actual source_drift refusals before the held-position timing behavior.

The test constructed a positive synthetic Selected runner using the default
source-pinned config. That config still binds original diagnosticse5e, so the
approved change to162f correctly fails the guard. Source comparison shows only
`scripts/demo_runtime/diagnostics.py` differs among that config's source paths.
An isolated rerun reproduces both refusals. The public source guard is behaving
correctly; weakening it or rewriting the Demo config would be the wrong repair.

The fixture now supplies existing `selected_config()` to both its initial and
restarted synthetic runner, matching neighboring Selected tests. No production
config or source binding was edited. The combined timing, new diagnostics and
selected-strategy suite passes35tests in2.947seconds with ResourceWarning fatal.
It includes `SelectedStrategyTests.test_source_drift_blocks_admission_frame_before_any_broker_call`,
which continues to prove refusal for a tampered source binding. Ruff passes.

The corrected-fixture full suite completed at31October05:58:14UTC with
1,630tests in268.372seconds, `OK (skipped=2)`, exit0. All531 source/test pins
are identical before/after; log SHA256 is
`b887d567e20e8c73aa46afa1e3d9ba4a61ae1ddc37a15334d50d483c41578954`.
The failed run, logs and pins remain preserved. Existing unclosed-database ResourceWarning
output in a different historical test is retained; this work does not silently
present it as fixed.

## Limits and next operation

This fixes a reproduced observability omission. The actual VM SQLite result
code, lock owner and deeper cause remain UNKNOWN. A synthetic BUSY/FULL fixture
does not select the VM failure class. Runtime errors predating the collector
cannot be attributed to that later collector; a later QEMU READ-lock snapshot is
not a causal historical witness.

The deployed diagnostics remain the observed olde5e hash. The deployed shared
runner and local timing-adjusted runner also differ. A later diagnostic rollout
requires its own exact intended-source manifest, approval, source/permission
binding checks, fresh safe exposure proof and backup/rollback. Do not copy the
dirty tree, apply constructor4465, change transaction/retry settings, accept a new
cost rate or force an order as part of instrumentation.

Evidence root:
`runs/c22-native-lifecycle-followup-2026-10-30/capture-2026-10-31/local-runtime-002c-implementation/`.
Read `focused-validation.json`, `fixture-correction-review.json`, the preserved
first `full-result.json`, and final `full-rerun-after-fixture/full-result.json`.
Root's applied-code review is recorded separately from the earlier independent
proposal review; no post-application agent review is manufactured. The operator continuation map is
`docs/ops/c22-claude-handoff-2026-10-31.md`.
