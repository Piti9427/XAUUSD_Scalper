# Selected26b8 diagnostics-only rollout preparation

Status: **LOCAL CANDIDATE BUILT AND FOCUSED-VALIDATED; NO VM DEPLOYMENT APPROVAL.**
The original goal remains20/23issues closed, with #13/#14/#34 open. This work
prepares instrumentation for the actual SQLite failure; it does not prove that
failure's native code or deeper cause, repair AP reconnects, accept a changed
cost rate or qualify future profitability.

## Exact candidate and preserved behavior

The original deployed-baseline archive SHA256 is
`11a8792f05d453664cf33c00f1e0bbfc4c8451ce4f0491152ea9fa1b4eb66a00`.
All87payload hashes and89regular members were rechecked. An isolated source root
was derived from that archive. The existing repository release generator, exact
builder SHA256 `8094c597b7a9877bff9f4234d6c54c1983452f03559df8a0fb3caccb35a5d7de`,
built the candidate from that root rather than the dirty checkout.

| Artifact | Verified value |
| --- | --- |
| Candidate release | `selected-f62a174bc1997fe1` |
| Candidate archive SHA256 | `6a77b78bd1ca4e083053443c1de3899fb878b798bda2ed48942459a8bab351f3` |
| Runtime source change | Only `scripts/demo_runtime/diagnostics.py`, e5e→162f, exact approved002c result |
| Required config change | Only `source_hashes.scripts/demo_runtime/diagnostics.py`; all other parsed config values unchanged |
| Candidate canonical config hash | `1ca974a4c0a13353c655c93cc73f9eab2961afa036448c12bedfd67029a9bb23` |
| Package validation | 87payloads,78Python in-memory compilations,25source bindings |
| Deployed shared runner retained | `ea904a373dbcbc7afd3832d93aeac7dff2aaf18cf90dcc0a8b636fe9a540fd19` |
| Deployed broker retained | `b84eef66a94af66872a6ac75eae0ac1fc123a3345dee9755f9443d8d688e9e30` |

Local midnight-timing changes, constructor patch4465 and other dirty-tree changes
are excluded. Native26b8, volume0.01, risk/daily/cooldown/protection and cost rules
remain unchanged. No operational permission/review was created.

## Candidate compatibility evidence

Ten existing portable diagnostic regressions run against imports from the actual
isolated candidate root and pass with ResourceWarning fatal. The driver asserts
the imported diagnostics, old runner and old broker hashes, then verifies the
candidate's exact source bindings before testing. It exercises Journal context
rollback, canonical CLI exit/shutdown/no-order and optional post-export put paths.

The earlier1,630-test/two-skip full PASS belongs to the canonical local tree.
It is not relabelled as a full result for this deployed-baseline candidate. Only
the actual isolated10-test result is claimed here. The candidate's diagnostic
bytes equal the independently reviewed approved patch result.

## Fresh read-only binding evidence

At31October06:06:06UTC (13:06Thai), a bounded read-only collector verifies all87
payloads of the existing release against its manifest and retains actual installed
sender unit bytes with SHA256
`2764cc011add28bd4c25a9aef5a34b4962d270982aba6d70e125f6524ddc8040`.
Verify the receipt before reuse. The
sender is active/running with restart counter127 at that time. Counter growth
does not assign one cause to every restart or prove broker exposure is flat.

The first collector refused the policy path as unsupported regular-file metadata
and returned no packet. It did not relax the guard. The installer source then
established the exact historical policy/review symlink targets. A separate V2
requires those exact targets and validates owner, private directory0700 and
regular target files0600, with post-read pointer checks. It succeeds. Both first
failure and later success remain retained; no pointer was changed.

The current documents match their previously approved bindings:

- Raw policy `07513b047e2aafe0ab227026494e7620753d7800f1c48385abbb6262aa7e6985`.
- Canonical policy `766539993467e9bf93b23b8f569a733de244587337d25ec7f8ba2abaa10e9ccb`.
- Raw review `1726e848809920770eda905e9340d65d0b66bb3641779da20e536b8383ec3a95`.
- Original review time29October09:20:46.969923UTC; existing168-hour policy expiry
  remains5November09:20:46.969923UTC. No time/rate/calendar was refreshed.

No SDK call, broker read, database access, remote file write, service restart,
order or policy acceptance occurred in this collection. Current flatness,
effective drop-ins, accepted journal marker and cost-incident state still require
their own execution-time checks. Actual latest swap drift remains a separate
admission blocker.

## Installed sender unit and source identity

The repository builder emits a base unit without the installed exporter argument.
It must not replace the actual unit blindly. A separate proposed unit is derived
from the verified current bytes by changing exactly two release-path occurrences:
WorkingDirectory and ExecStart's script path. All other bytes normalize identically;
the exporter flag, environment references, one-sender checks, restart settings,
lot/risk/cost arguments and delivery-OFF configuration remain.

Proposed unit SHA256:
`5a16e5792eec21f63c224d1186c048e7ce755828314d23e13aedb1adee233ce7`.
It is local only. Linux systemd verification has not run on the VM. Generated
terminal/watchdog/backup units are not selected for activation.

Diagnostics participates in both source and runtime identity. A new config hash,
runtime cohort and genuine source-bound execution review are required; reusing
the old review or disabling source checks would be wrong. The old cache sidecar
also binds the old config. Preserve it and allow genuine validated broker
bootstrap; do not forge a binding match. The existing new completed-M15-after-
approval rule remains in effect. No stale signal is replayed.

## Reproduced review recovery boundary

Four synthetic tests pass against review/cost/journal functions whose bytes are
asserted equal to the isolated candidate. They use temporary local state only:

| Requirement | Test |
| --- | --- |
| Before new acceptance, exact old review can resume | `test_before_new_acceptance_original_exact_review_still_resumes` |
| After new acceptance, stale old review refuses without changing the marker | `test_after_acceptance_restoring_old_review_is_stale_and_preserves_marker` |
| New-source review cannot authorize old-source cohort | `test_new_review_cannot_authorize_old_source_or_mutate_acceptance` |
| A separately authorized fresh old-source review can accept without policy renewal or marker reset | `test_synthetic_fresh_rollback_authority_accepts_without_reset_or_policy_renewal` |

An initial test-harness import failed because canonical test fixtures reference a
research helper deliberately absent from the small release. The final harness
uses canonical fixtures with byte-equivalence assertions for the tested validator,
cost and journal files. Both logs are retained; no missing runtime dependency or
VM success is inferred from that fixture import failure.

The owner is being asked to choose the post-acceptance recovery design. That is
not execution-time deployment approval. Before acceptance, exact original review
restoration can retain the existing accepted digest. After acceptance, neither
restoring a stale file nor resetting the journal digest is a valid rollback.
Preserve owned/UNKNOWN management whenever fresh flatness is unavailable.

## Remaining rollout requirements

An execution-ready operation still needs the selected recovery design, exact
source/cohort review construction, validated controller/cleanup paths, genuine
fresh Demo flat/noorders/noactive/noUNKNOWN/empty-outbox proof, current consistent
backup and restore checks, effective unit/drop-in checks and explicit execution-
time approval. Intentional entry pause remains at most15minutes per round.
No old financial journal, cost incident, peak, cutoff or loss state may be restored
or erased. No second SDK reader may compete with the sender.

Until these are complete, this is a reviewed local candidate and evidence package,
not a deployment instruction. After an approved rollout, an actual error code is
still needed before choosing a storage/locking fix. AP #13/#14 and external
delivery #34 retain their separate closure criteria.

Evidence root:
`runs/c22-native-lifecycle-followup-2026-10-30/capture-2026-10-31/claude-handoff/diagnostics-rollout-preparation/`.
Use `candidate-build-review.json`, final candidate/recovery test logs,
`current-binding-metadata-v2.receipt.json`, `sender-unit-candidate-review.json`
and the independent source-binding review. Preserve the original archive and all
earlier failed observations.
