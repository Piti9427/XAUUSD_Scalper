# C22 context diagnostics acceptance — Issue #9

Validated offline diagnostics for frozen `variant_1af968e9ac6a26ea` /
`RESEARCH-C22-H4EMA200-20261004`. Verdict:
**COMPLETE diagnostics; INCONCLUSIVE_FOR_FILTER_SELECTION**.
Trading rules, Demo configuration and account execution unchanged by this patch.

## Evidence

Campaign: `runs/c22-context-diagnostics-2026-10-05-final/`.
Original evidence: `data/research_output_four_strategy_full_history_2026_10_04/`.
167,366,065 ticks, 48,367 M15 bars, initial USD200 once per view.
All four complete unrounded results match original ledger, equity, risk admissions,
rejection counts and metrics exactly. Each instrumented result and annotation had
an independent fresh full-result repeat. Original source snapshots/input artifacts
and current instrumentation/transitive source hashes verified before and after run.

Protocol SHA256:
`4f33e94e56a72572534ba313510b2adb2055d5b2bd1eaf8d0b53d7385f233136`.

| View | Net USD | Return % | Max DD % | Trades | WR fraction |
|---|---:|---:|---:|---:|---:|
| base / no swap | 295.52 | 147.7600 | 39.07595 | 120 | 0.483333 |
| base / current-spec swap | 291.5482 | 145.7741 | 39.28073 | 120 | 0.483333 |
| stress / no swap | 246.8110 | 123.4055 | 37.61304 | 117 | 0.470085 |
| stress / current-spec swap | 278.7102 | 139.3551 | 37.82315 | 116 | 0.474138 |

Rounded display only; canonical JSON retains original precision. Swap sensitivity
can alter admission/equity and later trades, explaining nonmonotonic final results.
Costs remain assumptions, not verified historical broker parity.

Base/no-swap accounting: 834 raw signals (53 BUY, 781 SELL), 483 macro-blocked,
351 visited events: 120 admitted, 70 risk-cap, 36 daily-loss-count, 125 busy.
Every executed trade links once. There are 21 executed BUY and 99 SELL trades.
Rejected/macro-blocked records have no fabricated outcome or entry geometry.

Full archive lacks audited session coverage for complete day/week periods.
S/R and daily-range features therefore remain explicitly unavailable. Valid SD
uses last20 completed closes, population standard deviation, signal close included.
Base/no-swap SELL SD bins: adjusted z [0,2) has14 trades/net225.691; >=2 has85
trades/net-39.976. These are descriptive totals under original account path,
**not filtered-account results or evidence of a profitable threshold**. BUY samples
are sparse. All inspected history remains exposed discovery data.

## Validation and review

- Public feature/replay/CLI tests cover causal prefix/future invariance, UTC,
  nonfinite/warmup/zero variance, completed periods, quote/grid geometry,
  raw/macro/unvisited identities, outcome independence and both directions.
- Actual subprocess interruption after first artifact publication resumes through
  persisted payload journal. Input/source/protocol/checkpoint/artifact corruption
  blocks reuse and removes stale completion. Original fixture files preserved.
- Independent ledger/cash/risk/WR/PF/RR metrics reconcile. Exact DD witnesses retain
  determining peak/trough, including a regression where compressed equity
  endpoints/extrema alone miss local drawdown.
- Full repository suite: **876 tests, OK, skipped2**. Relevant prior suite:67 OK.
- Compile and dependency integrity pass. All five changed Python files pass lint
  and formatting. No typechecker configured in repository.
- Whole-repository lint blocked by unrelated pending unused `ROOT` import in
  `tests/test_c22h4_cli.py`; global format-check reports13 preexisting files.
  Those files were not included in Issue #9 patch.
- Standards review: original portable-fixture and interruption blockers resolved;
  no remaining blocker. Minor repeated replay argument bundles nonblocking.
- Spec review: original interruption and compressed-DD blockers resolved;
  no remaining blocker. Reviewer also reproduced COMPLETE publication crash
  recovery successfully.

Full four-view replay/repeat took247.61 wall-clock seconds according to
`/usr/bin/time`. macOS resource probe was denied `sysctl kern.clockrate`; peak
memory measurement unavailable. No unmeasured memory/speed claim made.

An earlier implementation campaign was truthfully BLOCKED after source changed
while running; it has no COMPLETE marker and is not acceptance evidence.
See [operator guide](../ops/c22-context-diagnostics.md) for run/resume protocol,
coverage assertions and diagnostic interpretation. Next research decision requires
verified coverage evidence and a separately frozen whole-account filter campaign.
