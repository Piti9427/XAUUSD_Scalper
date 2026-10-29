# Selected26b8 — bounded session-gap classification

Status: LOCAL IMPLEMENTATION AND HISTORICAL REPORT. Published T11 / GitHub #22.
No VM,SDK,service,order,cost policy,native H4 mapping or entry gate changed.

**The five preserved M15 gaps on26October2026 remain UNKNOWN because dated,
account-specific XAUUSDm session evidence is missing.** A new offline classifier
now explains that result,checks the original cache/provenance,and distinguishes
explicitly evidenced closures from gaps during declared open intervals. UNKNOWN
is the required outcome when external evidence is missing,not a claim that a
broker outage or scheduled closure was proved.

## Actual bounded report

Command executed:

```text
PYTHONPATH=. .venv/bin/python -m scripts.ops.c22_session_gaps \
  --capture-dir runs/c22-missed-signal-audit-2026-10-27 \
  --account-fingerprint <private-capture-fingerprint> --symbol XAUUSDm \
  --out runs/c22-session-gaps-2026-10-29/actual-report
```

Report creation:28October2026,18:22:20.000457UTC /29October01:22:20Thai.
Source capture observation:27October2026,03:23:56.309649UTC. The report is a
historical recheck,not current VM/feed evidence. Scope: five absent complete
M15 bars,open20:45,21:00,21:15,21:30,21:45UTC on26October,ending22:00UTC.

All five classifications are `UNKNOWN / dated_account_schedule_missing`.
Raw M1 minute membership is `NOT_CAPTURED`. In particular,the earlier13/15 M1
count used to reproduce the20:45bucket is a synthetic fixture,not a newly
observed minute-by-minute record. Missing M15 bars alone cannot identify every
missing constituent minute or prove the cause of absence.

The reader verified:

- Exact account fingerprint from the preserved journal identity and XAUUSDm
  from the captured config.
- Original6,666-bar CSV hash matches `cache_sha256` in the preserved snapshot.
  Actual hash: `ea6064878596bcbeb9359c9f3223ec802c2fd63b46c10596d4d29e80b5f1faf3`.
- Aware-UTC,ordered,unique,aligned complete M15 cache timestamps; declared
  missing bars are absent and match all cache gaps inside the stated window.
  Actual observed bars bound both ends. No synthetic candles were inserted.
- SHA256 bindings for the original snapshot,CSV and additional-evidence bytes;
  original observation time remains visible instead of being replaced by report
  time. Source files remain read-only.

Machine artifact:
`runs/c22-session-gaps-2026-10-29/actual-report/report.json`.

## Public classifier and evidence contract

New module: `scripts/ops/c22_session_gaps.py`. Public seams:

```python
classify_gaps(gaps, *, schedule=None, source_bytes=None,
              account_fingerprint=..., symbol="XAUUSDm", now=...)
capture_report(capture_dir, *, account_fingerprint=..., symbol="XAUUSDm", now=...,
               schedule=None, source_bytes=None)
```

Each observed gap is one missing M1 or incomplete/absent M15 interval. Schedule
input is an explicit packet with source kind `BROKER_ACCOUNT_SYMBOL_DATED`,
original capture time,raw source SHA256 and a document matching those exact
source bytes. The document binds schema,account fingerprint,symbol,UTC dated
coverage and explicit non-overlapping OPEN/CLOSED intervals with reasons.

Supported classifications:

| Evidence | Result |
|---|---|
| Entire gap covered by declared CLOSED intervals | `EXPECTED_SESSION_CLOSURE` |
| Entire gap covered by declared OPEN intervals | `UNEXPECTED_GAP_DURING_DECLARED_OPEN` |
| Partial OPEN/CLOSED overlap | `UNKNOWN / partial_open_closed_interval` |
| Uncovered date or interval | `UNKNOWN / schedule_dated_coverage_missing` |
| Missing schedule,raw bytes,account/symbol scope,UTC dates,valid source hash or unambiguous intervals | `UNKNOWN` with a specific reason |

The classifier binds supplied evidence; it does not independently authenticate
a broker response. `SOURCE_BYTES_BOUND` is not a new broker attestation.
Generic public trading hours cannot establish an account-specific schedule and
are rejected as `schedule_source_scope_unverified`. Synthetic schedule fixtures
remain synthetic. A gap during a declared open interval is unexpected against
that source; it does not by itself identify network,broker,extraction or retention
failure as the root cause.

Schedule windows are half-open UTC intervals. DST and holidays must appear as
actual dated intervals in evidence,not inferred from weekday or guessed offsets.
An adjacent boundary is valid; overlapping intervals are ambiguous and remain
UNKNOWN. A partial M15 overlap does not manufacture missing-minute information.
Source-missing is an evidence outcome. Malformed observed gap geometry or
contradictory cache provenance is rejected rather than turned into market data.

CLI output must be a new directory under ignored `runs/`. Existing reports are
not overwritten. This module imports only Python standard-library facilities
and has no broker,trade,delivery or runtime-configuration interface.

## Published acceptance criteria map

| Published #22 requirement | Evidence |
|---|---|
| Dated broker/session scope and aware UTC; generic public hours are not account proof | Source document/raw-byte binding,exact account/symbol/date/timezone checks; `test_generic_hours_wrong_account_symbol_or_tampered_bytes_cannot_attest` |
| Match actual M1/M15 gaps against schedule; missing or ambiguous evidence UNKNOWN | Actual five-gap report; `test_missing_dated_schedule_keeps_actual_gap_unknown`, `test_missing_date_inside_coverage_and_gap_after_coverage_remain_unknown`, `test_ambiguous_overlap_naive_dates_and_missing_fields_stay_unknown` |
| Fixtures cover rollover,DST,holiday and unexpected missing feed | `test_rollover_closed_minutes_and_open_market_missing_minutes_are_distinct`, `test_dated_dst_shift_and_explicit_holiday_are_not_weekly_guesses` |
| Preserve bounded session_unverified monitoring and native H4/entry rules | New offline module only; no existing runtime/pinned files changed. Actual report declares `native_rules_changed=false,candles_created=0,execution_authorized=false` |
| Cache and source provenance remain auditable | `test_actual_capture_reader_checks_cache_hash_identity_and_missing_bar_proof` verifies exacthash,identity,absence and source immutability |
| Boundaries,partial gaps and malformed inputs remain explicit | `test_adjacent_same_closed_intervals_cover_boundary_without_false_overlap`, `test_partial_m15_session_overlap_stays_unknown_without_raw_minute_membership`, `test_source_document_mismatch_duplicate_json_and_future_capture_are_unknown`, `test_bad_gap_or_duplicate_observation_is_rejected_without_creating_candles` |

Focused validation:13tests PASS; scoped Ruff PASS. Root independently reran all13 tests and repeated the actual historical report after final formatting at `runs/c22-session-gaps-2026-10-29/root-final-report/report.json`. The original agent report remains intact.
Agent work stopped at a usage limit; final review is root review, not an independent final certification. Final focused/compilation evidence is recorded under
`runs/c22-session-gaps-2026-10-29/`. Root later ran the fullrepository suite:
1507tests/266.355s,OK/skipped2; final receipt/log in
`runs/c22-forward-coverage-2026-10-29/`. No economic replay occurred. The remaining
external limitation is explicit: no
account-bound dated schedule or raw M1 membership was created by this work.
Consequently this report cannot justify a positive historical session-carry
decision for the separate H4 candidate or prove a missed profitable order.
