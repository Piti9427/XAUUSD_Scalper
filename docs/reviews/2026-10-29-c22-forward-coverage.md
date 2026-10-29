# Selected26b8 forward coverage companion — implementation complete, inputs incomplete

**LOCAL ONLY; GitHub#27 remains open.** A new standalone companion reads a
verified V2 sealed batch and its exact consistent SQLite backup,then produces
UTC daily record denominators and optional paired M15 cache provenance. It does
not connect to the SDK,modify the financial journal,change money calculations,
alter native26b8 or authorize execution. The frozen V2 collector and its original
artifacts remain byte-for-byte unchanged. No VM rollout or broker capture occurred.

## Actual bounded evidence

The companion and its verifier were executed against the original first
prospective collection batch,28October14:01:19.968493–14:02:27.420364UTC. The
backup SHA256 remains59034e1f1124334dc771bbc0167eb7e3f1f1cd89f6d749500bdf79092d29a760.
All38source rows match:37CYCLE/1HEALTH,28permission-blocked/unknown cycles,
0excluded rows. The daily row is partial,not a full trading day. No SIGNAL,
REQUEST,RESPONSE or LIFECYCLE was recorded in that bounded interval. Audit-kind
absence is explicitly listed; it is not an independently verified broker fill
count. Native fills,closed net and account cashflows stay null/NOT_CAPTURED.

Actual optional cache attachment is absent because no account/config-bound
CSV+metadata pair from that source interval was preserved. The older gap-audit
CSV alone is not upgraded into such a pair. Raw M1 membership and raw ticks
remain NOT_CAPTURED. The report does not create metadata,quotes,fills or zero
financial values to make coverage appear complete.

Artifacts: `runs/c22-forward-coverage-2026-10-29/actual-bounded-coverage/`,
including `coverage.json`; original batch/backup remain in
`runs/c22-issue-closure-2026-10-28/forward/`. Re-reading that already observed
collection history is not a new unopened validation sample. Qualification is
NOT_ESTABLISHED and execution_authorized=false.

## Public seams and trust boundaries

`scripts/ops/c22_forward_feed.py` exposes create_coverage,verify_coverage and CLI.
It reuses verify_batch against the consistent original backup before building
counts. Manifest/protocol/audit bytes are captured and rechecked after that
verification; changed bytes are rejected. Each daily row retains every source
audit ID,matched/excluded counts,kind counts,missing kinds,blocked reasons and
unknown cycles. Days are half-open UTC intervals with explicit partial edges.
Financial evaluation remains the existing sealed parent's responsibility;
this coverage companion makes no new cash/profit calculation.

Optional cache input must include the actual paired metadata emitted by
SelectedStrategy's existing save_manifest. Checks cover source bytes/hash,
account/config/contract/symbol/aggregation binding,strict metadata version/row
count,aware aligned unique UTC timestamps,finite positive OHLC geometry and
barclose<=original metadata creation<=report time. A torn/changed pair is rejected.
The companion copies original bytes privately; it never rewrites the source pair.

Cache data is labelled REUSED_CACHE_NOT_HOLDOUT even when some bar closes occur
after the collector freeze. That count cannot establish unopened collection or
prospective qualification. The producer's complete-M1 aggregation string remains
a source claim; constituent M1/tick verification is not inferred. Internal M15
gaps remain UNKNOWN without dated session classification. A source hash is
provenance,not independent broker authentication.

Output is a new private directory under ignored runs; copied files use0600 and
directory0700 through existing output helpers. Original evidence is read-only.
Verifier recomputes against the same original source backup and current module
hash; tampered copied cache,report,source batch or journal cannot pass silently.

## Reproduction,fix and validation

The initial agent feature test failed because the companion did not exist.
Root implemented the new seam,then reproduced an actual local prototype defect:
changing batch payload bytes after parent verification still gained a
source-bound label. `test_batch_change_after_parent_verification_cannot_gain_source_bound_status`
failed with ValueError not raised. The fix binds original bytes before/after
verification and checks their hashes against the parent result. This is a local
prototype failure,not a claim that deployed trading data was corrupted.

Focused companion10tests plus session13tests PASS23total. Scoped Ruff and
compilation checks PASS. Fullrepository suite1507tests/266.355s,OK/skipped2;
the wrapper records COMPLETE/exit0 at28Oct20:16:59.470396UTC. No test process
remains running. An earlier interrupted fullsuite has no successful terminal
summary and is retained without a PASS claim. No MT5 smoke test or actual
cashflow export is claimed. Agent usage limits prevented independent final
review; root reviewed assertions and source paths.

| Requirement | Exact evidence |
|---|---|
| Source/account/config/paired-cache provenance | `test_paired_cache_hash_binding_closed_bars_and_reused_labels`; `test_wrong_identity_hash_or_torn_pair_rejects` |
| Missing coverage never becomes zero money or tick proof | `test_daily_partial_windows_all_rows_missing_kinds_and_unknown_money`; actual38record report with null money/feed |
| Closed UTC bars and finite geometry only | `test_open_future_naive_or_duplicate_bars_never_count_complete`; `test_nonfinite_or_impossible_price_geometry_rejected_not_used_for_profit`; `test_scope_aggregation_and_future_metadata_never_attest_a_cache` |
| Changed inputs/tampered outputs fail | `test_change_during_pair_read_is_detected`; `test_batch_change_after_parent_verification_cannot_gain_source_bound_status`; `test_cli_and_tampered_attachment_or_report_cannot_pass` |
| Preserve originals | `test_original_inputs_unchanged_and_copied_cache_tamper_detected` |

## Remaining #27 work and concrete operational boundary

The existing selected-1c0453 sender already supports --broker-evidence-dir.
The last inspected execution unit does not pass that flag,so writing request.json
alone is inert. Enabling the existing export requires an argument-only sender
restart under explicit execution-time approval. It does not require changing
native strategy/source/config,lot,cost policy/expiry or terminal/runtime. A real
packet still must pass original Demo/account/flat/noorders/noactive/nohalt/
same-cycle-no-send/complete-epoch cash-and-volume/freshness gates. AP permission
failure can legitimately yield DEFERRED/broker_reads_incomplete; never bypass it.

Before any approved restart: fresh source/unit/policy hashes,consistent backup
and restore check,one-sender guard and no active/UNKNOWN intent; fresh exclusive
broker flat/noorders proof under existing ownership. No forced close. Retain the
old unit for argument-only rollback and the complete financial journal; no
financial-state rollback. If proof is unavailable,leave the sender/owned manager
in its safe current state. Account-level exposure is not inferred from local
journal emptiness. A pending notification queue is not an order queue.

Actual source-bound cache and broker ledger attachment remain missing,so this
companion alone does not close #27 or qualify #32. Genuine native signal→fill→BE→
close remains a separate #25 observation; no forced trade is proposed.

## Later actual paired-cache collection —29OctoberThai

The missing-cache statement above describes the first38-record source batch.
A later read-only collection now supplies an actual stable CSV+metadata pair
and a new consistent journal backup. No SDK call,VM file write,restart or private
environment/credential read occurred. The original first batch was preserved.

New sealed window28Oct14:02:27.420364–20:23:12.319328UTC contains13,693records,
all matched:13,272CYCLE/371HEALTH/25SIGNAL/25STATE,0excluded;10,480cycles retain
unknown protection/status coverage. It is one partial UTCday,not an independent
trade sample. Source backup SHA256
38db43dc054eff973d5564aeedfb217d59b709ad52dbb98de59783226095a9d8.
Parent V2 verify_batch plus companion verify_coverage both PASS against that
exact backup.

Actual cache metadata was created20:15:07.919757UTC,6,632complete claimed M15 bars,
first17July16:15UTC,last28October20:00UTC. The pair's source/config/account/hash/
UTC/closed-bar/geometry bindings pass.25bar closes follow the collector freeze,
but the report still labels the whole cache REUSED_CACHE_NOT_HOLDOUT; neither25
signals nor25postfreeze closes is a qualifying prospective trade sample. Actual
raw M1/tick membership remains NOT_CAPTURED and broker ledger remains absent.
Artifacts: `current-source-batch/`,`current-source-coverage/`,original CSV/meta,
read-only-source-receipt and lifecycle-count-audit under this campaign's runs.

Full sender-journal aggregation contains no REQUEST,RESPONSE or LIFECYCLE kind.
Its7FULL SELL signal identities have first-cycle refusals5cost-policy gates and
2first_quote_unknown,all bound to the older release/config cohort. Do not infer
the exact historical mismatching cost field from those old generic refusals,
or call an unexecuted signal profitable. Sender outbox is0,active intentfalse,
haltfalse at this backup; none proves current broker account flatness. Account-
wide manual activity remains outside this journal proof. #25/#27 stay OPEN.
