# C22 diversified research loop

Run from repository root using the same Python/numpy/pandas runtime throughout:

```bash
python3 -m scripts.research.c22_tuning_loop --output runs/c22-tuning-loop-2026-10-07 --workers 4
```

Repeat exact command to resume. `--max-cells N` bounds new cells for one invocation;
it does not change the 300-config campaign budget or qualification. Completed
cells are verified and reused; no new cells are required to resume a completed loop.
Source/config/runtime changes invalidate resume. Preserve frozen snapshots rather
than editing prior campaign artifacts. Input acquisition requires network access;
missing or unsupported swap metadata blocks economic results.

Configuration: `config/c22-tuning-loop.json`. Search contract:
`specs/c22-tuning-loop.md`. Each campaign contains input, frozen source snapshot,
search protocol/catalogs/cells/repeats/checkpoint and COMPLETE/BLOCKED marker.
Root loop-state binds prior provenance, cross-campaign catalogs and completion.
At least5GiB free disk is required before an incomplete loop starts. This is an
operational preflight, not an economic gate; disk can still fill during replay.
If sources change after a blocked attempt, preserve that attempt's search,
source_snapshot and loop-state separately before starting a new protocol.
Loop max: three campaigns, 300 new variants each. Qualification remains unchanged;
all results retrospective and COST_INCONCLUSIVE. Demo untouched, real money prohibited.
