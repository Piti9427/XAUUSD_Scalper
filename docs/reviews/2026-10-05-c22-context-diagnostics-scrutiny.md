# Outsider scrutiny — C22 diagnostics commit 8b33708

Goal: measure frozen C22 decision context without changing trading results.
A smaller ledger-only annotator would lose raw/rejected signal identities; existing
post-replay annotator plus opt-in identity capture is justified. No broader strategy
implementation or proprietary indicator surface is needed.

Verdict: **FIX-THEN-SHIP**. This review supersedes the previous “no remaining
blocker” conclusion for campaign operability; previously verified four-view
baseline parity remains valid for that unchanged, single-writer acceptance run.

## Major / P2 — Two writers overwrite campaign progress

Source: `scripts/research/c22_context_campaign.py:204`, journal publication at444,
artifact/checkpoint commit at445–450. Entry has no exclusive campaign lock. The
shared writer `scripts/research/reward156_tuning.py:44` also uses the same `.pending`
filename across callers.

Reproduction: start caller A with max_cells1; pause it immediately after publishing
first pending-cell checkpoint. Caller B resumes same directory, recovers pending
cell and completes all four views. Release A: it overwrites checkpoint with its
older one-cell state and returns PARTIAL. Next ordinary resume exits1 with
`BLOCKED: uncommitted completion mismatch`. Completed research work is no longer
resumable without creating a new run.

Minimal fix: nonblocking exclusive advisory lock for the entire campaign directory
validation/write lifetime; reject second writer before mutation. Use an OS-backed
lock which releases after process death. Add two-subprocess race/crash tests.
Atomic file replacement alone is not mutual exclusion.

## Major / P2 — Wrong JSON type bypasses failed-validation cleanup

Source: `scripts/research/c22_context_campaign.py:259` invokes `.get` before
validating checkpoint shape; exception cleanup at476 only handles ValueError,
OSError, KeyError and StopIteration. CLI handler at493 uses same limited list.

Reproduction: complete small real-detector campaign, replace checkpoint.json with
valid JSON `null`, invoke same CLI. Exit1 raises
`AttributeError: 'NoneType' object has no attribute 'get'`. No structured BLOCKED
result appears, and stale COMPLETE.json remains present despite invalid evidence.
This contradicts the failure/completion contract. Similar wrong-type baseline
objects can raise TypeError before the cleanup path.

Minimal fix: validate decoded JSON object/container and field types before
operations, normalize malformed persisted-input errors into declared validation
exception, and invalidate completion consistently for every failed validation.
Add null/list/wrong-nested-type CLI tests asserting BLOCKED and no COMPLETE.

## Verification scope

Traced CLI → original/source/input verification → checkpoint recovery → candidate
and closed H4 detector → public replay/account guards → observational identity/DD
capture → causal context → authoritative ledger join → bins → completion.
Existing targeted suite executed:13 tests OK. Both defects reproduced through
real synthetic CLI fixtures, manipulating only filesystem/publication boundaries.
No detector, entry plan or trading state was mocked. No implementation edits.
Original full historical campaign was not modified or replayed during this review.

Evidence: `runs/c22-context-scrutiny-2026-10-05/probe.py` and
`runs/c22-context-scrutiny-2026-10-05/reproduction.jsonl` (ignored machine artifacts).
Temporary campaigns were removed after each probe; original evidence preserved.

## Follow-up

The two findings are addressed in the subsequent campaign-lock/validation fix;
see [fix verification](2026-10-05-c22-context-campaign-fix.md). The findings and
reproductions above describe original commit8b33708, not the corrected version.
