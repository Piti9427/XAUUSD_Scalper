# Research preparation and supervision refactor

Scope: behavior-preserving implementation of `/tmp/xauusd-research-handoff-2026-10-03.md`.
Research only. Existing trial30 Demo settings, execution adapters and notifications
were not modified. No qualification, cost parity or profitability claim follows.

## Structure and compatibility

`bidirectional_campaign.main` keeps its CLI, loader/date/qualifier globals and
resume checks. Public `candidate_frame`, `contracts`, `qualifies_trial30`, `metrics`,
`Rules`, `Costs`, `features` and `replay` imports remain available at original paths.

| Responsibility | Module |
| --- | --- |
| Campaign orchestration | `bidirectional_campaign.py` |
| Causal challenger preparation | `campaign_signals.py` |
| Scenario gates and executed metrics | `campaign_qualification.py` |
| Catalog dispatch / recursive seed lookup | `campaign_catalogs.py` |
| Frozen families | `catalog_m5.py`, `catalog_annual.py`, `catalog_parent.py`, `catalog_hybrid.py`, `catalog_basic.py` |
| Shared catalog rule constructor | `catalog_common.py` |
| Replay contracts / signals / admission | `breakout_models.py`, `breakout_signals.py`, `breakout_entry.py` |
| Tick event loop | `breakout_replay.py` |
| Legacy public imports | `breakout_logic.py` |
| Bounded subprocess lifecycle | `supervision.py` |

Every extracted campaign/replay implementation file is included in protocol source
hashes and frozen snapshots. Old protocols intentionally fail resume equality;
do not rewrite old evidence to make it compatible. M5 builder provenance also
invalidates old caches because its source changed. Use a fresh output directory.

M5 preparation caches setup tuples and available UTC timestamps, replacing repeated
Series materialization and DatetimeIndex scalar access. Entry math preserves float
operation order, Decimal floor sizing, fee-inclusive risk checks and rejection order.
Strict boundary equality, actual-timeframe prior-day mapping, causal setup availability
and completed-M15 management remain unchanged.

## Subprocess CLI

Run `PYTHONPATH=. .venv/bin/python -m scripts.research.supervision --jobs jobs.json`.
Paths resolve from invoking directory; each job can set `cwd`. JSON contains a list:

```json
[
  {
    "command": [".venv/bin/python", "-m", "scripts.research.bidirectional_campaign", "--dataset", "data/b1_public_exness_2025_10_2026_09", "--output", "data/new-research-campaign", "--catalog", "annual_directional_fine", "--limit", "1", "--require-calendar-year"],
    "log": "logs/new-research-campaign.log"
  }
]
```

Default workers=2, child timeout=7200s, snapshot timeout=120s. Optional `snapshot_root`
waits for all protocol source snapshots to match before starting a verifier. Put
producers before dependent verifiers, with enough workers for both; readiness waits
occupy worker slots. Use independent output directories and unique logs. Commands
execute directly without a shell; environment is inherited. CPU replay stays inside
child processes. Failure cancels siblings, terminate escalates to kill after5s and
wait reaps children, including repeated cancellation and cancellation during spawn.
Supervisor owns direct children, not arbitrary descendant process trees.

## Reproducible evidence

[Audit script](artifacts/2026-10-03-research-refactor-audit.py.txt) loads archived
before-source files and current modules, verifies input hashes, then checks exact
complete results. [Evidence JSON](2026-10-03-research-refactor-evidence.json) records
source/input hashes, scenario hashes, alternating timings and traced allocations.
Catalog fixtures capture all46 families /5,402 ordered contracts before extraction.
Annual data:23,230 complete M15 bars,70,460 complete M5 bars,104,133,248 Bid/Ask ticks.
No holdout accessed.

Observed exact parity: all catalogs; four M5 TTL2/4 × both/BUY-only frames including
dtypes/column order;18 whole-result annual base/stress full/half scenarios across
trial30, equity-risk sizing and M5 trigger stops. This verifies tested cases, not
every possible replay input or broker runtime behavior.

M5 alternating five-run median: before2.311s → after0.256s,9.04× faster on this
machine/input. Tracemalloc peak grows65,626,211 →70,910,144bytes (about8.1%) due to
cached setup tuples/timestamps. Benchmark excludes tracing.
This is preparation speedup, not whole-campaign or live latency speedup.

Validation: scoped public replay/campaign tests, real subprocess lifecycle tests,
Ruff, scoped mypy (`--ignore-missing-imports --check-untyped-defs --follow-imports skip`;
pandas stubs absent). Full suite:800 tests,798 pass,2 skipped. Two-axis code review
against `develop` plus current refactor: Standards0 findings; Spec identified one
stale supervisor evidence hash after Python3.10 timeout compatibility adjustment.
Hash refreshed after six real-process lifecycle tests and manifest CLI verification;
remaining Spec findings0. Python3.10 interpreter itself was not exercised.
