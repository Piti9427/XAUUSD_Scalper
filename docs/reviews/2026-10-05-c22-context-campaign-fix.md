# C22 context campaign lock / validation fix

Scope: fix two operability findings from [scrutiny](2026-10-05-c22-context-diagnostics-scrutiny.md)
of commit8b33708. C22 detector, trading rules, risk and replay source unchanged.

## Root causes and corrections

Concurrent callers shared journal state and `.pending` filenames without mutual
exclusion. Atomic rename protected individual files, not campaign transactions.
A paused owner could overwrite a second caller's newer completed checkpoint.
The public campaign entry now acquires a nonblocking `fcntl.flock` exclusive lock
before validation, recovery or publication. The OS releases ownership on process
death; the empty lock file retains its inode. A rejected contender never enters
owned failure cleanup and leaves active artifacts/COMPLETE unchanged.

JSON decoding does not guarantee a dictionary. Resume called `.get` on decoded
`null`, causing AttributeError before narrow cleanup/CLI handlers. The JSON input
boundary now requires an object. Owner failures invalidate stale completion before
propagating; CLI normalizes malformed container failures into structured BLOCKED.
Checksum-valid wrong nested types are tested too, rather than assuming only bad
syntax or digest corruption can happen.

## Diagnosis evidence

- Public CLI regression command initially failed both target tests in1.667s.
- Pdb inspected actual failure: checkpoint NoneType at old line259; COMPLETE exists.
- Ranked hypotheses: missing exclusion; wrong-type validation order; general
  digest failure; replay nondeterminism. Disproof controls ruled out latter two:
  sequential complete/repeat succeeded; malformed syntax and `{}` correctly
  blocked/deleted COMPLETE, while `null` did not.
- Original reproductions now return null-checkpoint BLOCKED/no COMPLETE and
  concurrent-contender exit1 while owner resumes to COMPLETE. No trading mocks.

Machine experiment ledger/logs: `runs/c22-context-fix-2026-10-05/`.
Temporary debug scripts remain clearly marked in ignored scrutiny run directory;
no debug instrumentation added to production source.

## Regression evidence

| Requirement | Exact public test |
|---|---|
| Reject competing writer before evidence mutation | `test_second_writer_rejected_without_mutating_active_campaign` |
| JSON null blocks and invalidates completion | `test_invalid_checkpoint_type_blocks_and_invalidates_completion` |
| Wrong nested fields and object types fail closed | `test_malformed_persisted_types_all_block_and_invalidate_completion` |
| Process death releases ownership; contender keeps COMPLETE | `test_lock_released_on_process_death_and_contender_keeps_completion` |
| Actual publication interruption remains resumable | `test_process_interruption_during_artifact_publication_resumes` |

All tests above live in `tests/test_c22_context_campaign.py`.
Targeted command: `.venv/bin/python -m unittest tests.test_c22_context tests.test_c22_context_campaign`
— **17 tests OK**. Full repository suite: **880 tests OK, skipped2**.
Compile/dependencies and changed-file lint/format pass. Whole-repository lint still
finds unrelated pending unused ROOT import; global format-check still reports13
preexisting files. Those changes remain outside this fix.

## Prevention and boundary

Campaign ownership is now established at the public CLI seam. Future writer
changes must keep lock acquisition before recovery/publication and include real
multi-process tests. Persisted JSON must be treated as untrusted typed input,
including syntactically valid null/list/container values. No new architecture or
trading abstraction is required for these fixes. Lock support is macOS/Linux;
Windows offline portability is outside this existing workstation workflow.

## Corrected-source historical acceptance

`runs/c22-context-diagnostics-2026-10-05-locked/` completed all four archived cost
views on167,366,065 ticks /48,367 M15 bars. Every full original trading result
matches exactly; every instrumented result and annotation has a fresh full-result
repeat. Trade counts remain120/120/117/116. Resume returns COMPLETE with every
artifact digest unchanged. Full replay/repeat took230.25 wall-clock seconds;
no memory measurement claimed.

Protocol SHA256:
`f149d24f24a66fe2e3e3b5c90876f2ca9ef0daf678fd0c7c1dfc99fc5d2358d7`.
Verdict: **SHIP for offline diagnostics**. `INCONCLUSIVE_FOR_FILTER_SELECTION`
remains: full-period coverage evidence is unavailable. This fix neither selects
filters nor changes Demo operational qualification.
