# C22 context diagnostics

Offline implementation of [Issue #9](https://github.com/Piti9427/XAUUSD_Scalper/issues/9)
and [PRD](../specs/2026-10-05-c22-context-diagnostics-prd.md).
Frozen snapshot: `RESEARCH-C22-H4EMA200-20261004` /
`variant_1af968e9ac6a26ea`. No broker API, entry filters or Demo configuration changes.

## Run and resume

From repository root, with original ignored archive artifacts available:

```bash
.venv/bin/python -m scripts.research.c22_context_campaign \
  --output runs/c22-context-diagnostics-2026-10-05-swap-only
```

On macOS/Linux, one process owns the campaign through a nonblocking OS advisory
lock held for the entire validation/recovery/write operation. A competing CLI
returns `BLOCKED: campaign already running` before changing evidence, including
an existing completion marker. Process death releases the OS lock automatically.
The empty `.campaign.lock` file remains as a stable inode; never delete it while
writers could be active. It is synchronization state, not a research artifact.

Decoded protocol/checkpoint/baseline JSON must be objects. Invalid object/container
shapes return structured `BLOCKED` and invalidate stale completion under the owner
lock. Unexpected failures also invalidate completion before propagating. A lock
contender does not perform this cleanup because it does not own the campaign.

Repeat the same command to resume. `--max-cells 1` bounds a session to one new
cost-view cell; each cell still performs a fresh full replay and full-result repeat.
Owner policy2026-10-05: new backtests always include modeled swap. Only
`base-swap` and `stress-swap` run; both are mandatory for `COMPLETE`.
Protocol schema2 explicitly pins these two views and `swap_required=true`.
Missing/unsupported broker swap data blocks the run; there is no no-swap fallback.
Older four-view directories are immutable historical evidence; use a new directory
for this protocol. Shared replay unit regressions retain their mathematical/API
coverage; no-swap outcomes are excluded from new economic comparisons. A changed source, input, protocol or
published artifact returns `BLOCKED`; use a new campaign directory after reviewing
the change. Original evidence is never overwritten. Do not manually repair digests.

A pending journal persists complete validated cell payload before artifact
publication. Following interruption, matching published bytes are retained,
missing bytes restored, and checkpoint committed. Atomic-writer `.pending` bytes
are owned temporary outputs, never baseline evidence. Completion publication also
recovers across interruption. Corrupt pending or completed evidence blocks reuse.

## Outputs

`protocol.json` binds archived sources, input/proof hashes, current transitive
application-source hashes, runtime versions and coverage evidence. Frozen source
snapshots must match. One known preexisting migration of reward156 campaign output
from `docs/reviews/` to `runs/` is accepted only when the remaining source bytes are
identical; the current digest is recorded separately. Replay instrumentation is
versioned separately and must reproduce every original trading field exactly.

Each cost-view directory contains:

- `diagnostics.json`: raw signal identity, macro/admission reason, immutable feature
  values, authoritative ledger geometry, and subsequently joined outcome.
- `coverage.json`: all-signal, visited-event and executed-trade denominators;
  BUY/SELL distributions using predeclared bins, including missing categories.
- `validation.json`: baseline artifact reference, full-result parity/repeat,
  independent ledger/metric/risk reconciliation, and exact drawdown witnesses.

Drawdown witnesses retain actual running peak and subsequent trough determining
new drawdown records. Reconciliation computes `(peak-trough)/peak`; compressed
legacy equity checkpoints alone cannot reconstruct every intrasegment drawdown.
Default replay outputs remain unchanged; opt-in observation adds `context_events`
and `context_dd_witnesses` only.

`checkpoint.json` verifies its canonical bytes, payload checksum and every owned
artifact digest. `COMPLETE.json` identifies diagnostic completion, always with
`INCONCLUSIVE_FOR_FILTER_SELECTION`. This status is not profitability qualification.

## Coverage evidence

Without verified session coverage, S/R and daily-range features remain null with
`coverage_unavailable`; SD still uses last20 completed M15 closes. Complete monthly
files and ordinary candle counts cannot prove complete trading days/weeks.

Optional `--coverage path/to/coverage.json` accepts explicit fully covered UTC
period starts with provenance:

```json
{
  "provenance": "Reference to audited session calendar and missing-data evidence",
  "days": ["2026-01-05", "2026-01-06"],
  "weeks": ["2026-01-05"]
}
```

Days require all expected trading observations, excluding partial archive-edge
periods. Weeks start Monday and require the entire immediately preceding calendar
week. Scheduled closures require evidence; do not mark missing periods complete.
The campaign hashes the supplied file. This file is an operator evidence assertion,
not an automatic session-calendar verifier. No such coverage assertion currently
exists for the full archive; do not fabricate it merely to populate features.

## Interpretation

Open S/R, daily-range and SD proxies are not proprietary indicator reproductions.
All inspected archive history is discovery data. Bin totals describe executed
trades under original C22 account path; they cannot show what account equity would
be after filtering. Sparse BUY samples and missing period context prevent filter
selection. A later filter campaign needs a separate frozen catalog and whole-path
replay. Demo promotion requires separate operational approval and gates.
