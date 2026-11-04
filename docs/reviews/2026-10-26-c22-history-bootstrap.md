# Selected26b8 history preload and precise H4-gap status

## Summary

Selected26b8 already read historical M1 at startup. The actual VM had6,588 complete
M15 bars from15July2026 and361 complete H4 bars; it was not waiting for201 new
live H4. Its latest closed Sunday H4 contained only7of16 M15, so the frozen macro
mapper deliberately returned NaN. A generic macro_warmup_insufficient label hid
that distinction. The exported history also was not restored on restart.

The operational fix adds a verified restart seed, bounded retry for genuinely
short SDK history and a distinct macro_latest_h4_incomplete diagnostic. Native
Rules26b8bcd69e043653, invalid-H4 gating, signals, levels, fixed0.01, risk/costs,
daily/cooldown and position management remain unchanged. This is not a new
economic strategy or profitability result. Operational deployment evidence is
retained under runs/c22-history-bootstrap-2026-10-26 and
runs/c22-history-bootstrap-retry-2026-10-26.

## Symptom and reliable reproduction

Read-only export from the running VM at09:21:26 Asia/Bangkok:
CSV SHA25628da3f8c24a62b469637c4ec2937d1852b4e3581dd65d8b95316d19d01772d3d,
6,588 bars ending26October2026 02:00UTC. Calling the original
SelectedBarCache.append on those exact bars reproduced
macro_warmup_insufficient despite361 complete H4. The current last decision was
02:15UTC; the prior20:00UTC Sunday bucket had7 bars. The same source prefix before
that gap had a finite macro. Merely downloading more old history cannot repair
the incomplete latest bucket.

201×4hours=804hours=33.5 continuous24hour days; actual market-calendar coverage
is longer because trading closes and incomplete buckets do not count. These are
historical bars, not a required wait after launching. In this captured Monday
example, next scheduled H4 close is04:00UTC=11:00Asia/Bangkok, conditional on all
16 complete M15 arriving. Every other entry gate and the strategy signal still
must pass afterward.

## Root cause and mechanism

SelectedStrategy.frame fetched100,000 recent M1 in50,000-bar pages when its
in-memory cache was empty. SelectedDemoRunner exported that cache to CSV but
never loaded it back. A service/process restart therefore repeated the full
broker bootstrap. Also, a short first SDK response initialized cache.bars before
warmup failed, so subsequent calls could stop retrying the historical bootstrap.

SelectedBarCache.append used the same error for fewer than201 complete H4 and
NaN in the current mapped macro. closed_h4_ema in the frozen research source
publishes complete H4 EMA only at H4 close, and reindexes invalid/empty H4 buckets
to NaN. It intentionally does not carry Friday's last finite EMA through an
invalid Sunday bucket. This rule explains the Monday block; it is not removed.

No debugger attached to the armed VM manager. The exact exported CSV provides a
fast deterministic local repro; source tracing and differential prefixes then
isolated the two branches without interrupting its active/UNKNOWN manager path.

## Fix

- [history.py](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/history.py)
  binds a sidecar to account fingerprint, symbol, Rules ID, aggregation version,
  canonical runtime config/source digest, CSV hash, UTC range and row count.
  It validates positive finite OHLC, UTC chronology/alignment/completion and exact
  overlap with freshly aggregated broker M1. A bad/missing seed falls back to
  historical broker bootstrap; arbitrary CSV alone is not trusted.
- [strategy.py](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/strategy.py)
  restores the verified prefix and appends fresh bars. Genuinely short history
  retries at most once per60seconds. History backfill preserves all known bars;
  changed/missing overlap produces an explicit blocked reset before a rebuild.
  Sufficient history with a partial latest closed H4 does not refetch old history.
- [runner.py](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/runner.py)
  checkpoints metadata after the existing atomic CSV export. Metadata failure
  cannot stop an owned active/UNKNOWN position manager. The financial journal,
  equity/day baseline, orders, permissions and cost-policy expiry are not reset.

New diagnostics include complete_h4_bars,required_h4_bars,prior_h4_open_utc,
prior_h4_m15_count,next_h4_close_utc and history_seed_status. Missing old seed
metadata or a new source/config version causes one verified cold rebuild. On
later restarts, fresh broker overlap remains mandatory; live quotes/account/
history are never replaced by cached financial state.

## How it was found and why it slipped through

The hypothesis of insufficient total history was disproved by361 complete H4.
Comparing the prefix before the last gap against the exact latest prefix proved
that prior closed-bucket completeness determines macro availability independently
of historical warmup. Existing tests covered short3200-M15 history but did not
distinguish an incomplete latest *closed* H4 from a partial *forming* H4. Existing
CSV export tests proved writes and repairs, not restart restoration.

Focused tests and independent review also exposed two implementation issues:
non-object JSON metadata initially raised AttributeError instead of cold fallback,
and an intersection-only retry merge could drop previously validated bars. Dict
validation and symmetric overlap preservation fixed those cases before staging.

The first exclusive VM preflight exposed another real platform difference:
native broker aggregation used datetime64[s,UTC], while CSV parsing restored
datetime64[us,UTC] on Windows Pandas. Strict full-series equality rejected this
before the new sender was started. The controller restored the old reviewed
manager; no order or financial-state reset occurred. The fix normalizes the
validated seed index to the fresh broker index's resolution and name. It also
rejects submillisecond misalignment before normalization, preventing rounding
from concealing a malformed timestamp. Two regressions reproduce these failures.

## Validation

- Final focused history suite:25 tests,9.037seconds,exit0; independent reviewer
  reran the same25 tests in8.672seconds,exit0.
- Selected strategy/runner/cache/release/boot/lifecycle regression group:
  62 tests,42.513seconds,exit0.
- Final full repository suite:1,227 tests,250.305seconds,exit0;2 existing skips.
- Scoped Ruff and Python compilation pass.
- Exact real VM prefix restored locally with0 full-history calls and identical
  entire direction/macro series; latest-incomplete-H4 block preserved.
- Fresh archive price agreement:49,729 bars and2,751 admitted entry geometries
  across6 retained cost/counter paths pass. This shares canonical helpers and is
  not independent economic validation, a lifecycle replay or fresh broker parity.
- All101 frozen research source hashes remain unchanged. Native Rules/contract
  and archived research proofs remain unchanged; current operational binding
  includes the additional history module.

| Owner requirement | Concrete evidence |
| --- | --- |
| “ตั้งให้เป็นอ่านย้อนนับจากตอนที่ run” | test_short_bootstrap_retries_after_60_seconds_when_sdk_history_expands; historical M1 paging remains anchored at latest broker data |
| “แทนที่จะมาอ่านใหม่ตอน run bot ทุกครั้ง” | test_restored_strategy_matches_native_full_frame_without_full_history_fetch; real-prefix-restart-parity.json reports0 full-history calls |
| Do not treat old complete history as current H4 readiness | test_many_complete_h4_but_latest_closed_bucket_partial_has_specific_blocker; test_forming_partial_h4_does_not_hide_previous_complete_closed_macro |
| Preserve owned protection on cache failure | test_checkpoint_write_failure_does_not_disable_owned_position_manager exercises actual FILLED→MANAGING cycle |
| Reject modified/omitted known history | test_retry_bootstrap_rejects_known_overlap_omission_and_changed_price; test_retry_bootstrap_retains_known_older_prefix_when_fresh_window_slides |
| Keep native timestamp precision without rounding malformed timestamps | test_valid_seed_preserves_broker_datetime_resolution; test_submillisecond_offset_rejected_before_publishing_or_restoring_seed |

Tests: [focused regressions](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/demo/test_c22_selected_history.py).
Evidence: [captured VM input](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-history-bootstrap-2026-10-26/vm-snapshot-before.json),
[H4 gap witness](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-history-bootstrap-2026-10-26/macro-gap-witness.json),
[restart parity](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-history-bootstrap-2026-10-26/real-prefix-restart-parity.json),
[final full test log](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-history-bootstrap-retry-2026-10-26/full-unittest.log),
[final archived price agreement](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-history-bootstrap-retry-2026-10-26/archive-parity.json).

## Operational boundary

The final staged immutable release is selected-98c2c73ed40ae408,80 verified files.
Demo cutover uses source-bound owner review, current unchanged cost policy,
verified Mac-restorable backup, revoked admissions followed by a flat completed
cycle, one stopped sender and exclusive read-only broker/history probes. A new
source cohort is recorded without resetting the continuous financial journal.
Actual deployment/startup results are separate from the local test claims above.

The first attempt stopped safely at its timestamp-resolution assertion before
new-sender startup, then restored the old reviewed manager. The corrected r2
cutover completed26October2026 13:22:00Asia/Bangkok. Its exclusive broker probes
confirmed the same43 deals, flat exposure and balance/equity$1,811.97. Cost-policy
bytes and expiry were preserved. Execution PID49393 uses
selected-98c2c73ed40ae408; persistent terminal PID34838 was not restarted.
The actual CYCLE release/config hashes and persisted review hash match the new
cohort. Execution/terminal boot registrations, local watchdog and existing backup
timer point to this release; external delivery remains disabled.

Real Windows MT5 data cold/warm comparison passed on6,587 complete M15 bars with
361 complete H4. Cold bootstrap made two50,000-M1 requests and took50,956ms;
validated warm restoration made zero full-history requests and took5,181ms,
approximately9.84× faster for this measured stage. This excludes terminal startup,
ordinary fresh-data reads, account/history verification and order execution.
Direction and macro EMA series agree across the whole identical input prefix.
This is neither a broker latency guarantee nor a profitability result.

A source/config change invalidates the previous seed binding and can require one
cold rebuild. That100,000-M1 SDK window moves with time, so this new seed starts
15July2026 13:30UTC, later than the old continuously running prefix. Agreement
above compares cold and warm calculations on the same input; it does not assert
bit-identical EMA to an older, longer prefix. Subsequent same-cohort restarts keep
the validated older prefix and add fresh bars, avoiding repeated rolling-window
reinitialization. No missing bar is fabricated to equalize histories.

After source reapproval the unchanged execution gate requires an M15 close after
approval, making13:30Asia/Bangkok the next eligible scheduled close. It does not
require201 new H4; ordinary restart with the same review does not reset approval.
The reconstructed UTC-day baseline remains$1,812.21, not current$1,811.97.
The new-cohort consistent backup was downloaded and independently restored on
Mac:11kv rows,0events,38,753audit events, integrity check and source/review hashes
verified. Initial raw download timeouts retained partial copies; transferring a
gzip artifact and verifying both compressed and original hashes completed the
restore without altering the financial journal.

VM evidence: [cutover](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-history-bootstrap-retry-2026-10-26/cutover-result.json),
[real cold/warm comparison](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-history-bootstrap-retry-2026-10-26/history-preload.json),
[boot/watchdog/backup binding](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-history-bootstrap-retry-2026-10-26/boot-and-watchdog.json),
[independent Mac restore](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-history-bootstrap-retry-2026-10-26/backup-after-mac-restore.json).

## Final observed runtime

At26October2026 13:30:55Asia/Bangkok, the actual running execution service reports
history_seed_status=restored,6,588 complete M15,361/201 complete H4 and finite
macro EMA4205.686851519499. The latest cycle is WAIT/duplicate_bar,execute=true,
critical=false: it has passed the historical and newly closed-M15 gates and is
waiting for a new decision bar. This does not assert a qualifying entry signal
or order fill. The prior closed H4 has16/16 M15. The checkpoint CSV and sidecar
hash/range/source/account binding match the current frame and cohort.

Execution PID49393 and terminal PID34838 remain active, enabled,0 restarts.
Competing selected/legacy senders and shadows are inactive. No owned position,
halt or unsent event is present; equity remains$1,811.97 and UTC-day baseline
$1,812.21. The local watchdog reports HEALTHY with no findings and delivery
disabled. The verifier only reads the journal, unit metadata and cache; it makes
no broker call or order. Its first observation caught the expected brief interval
between atomic CSV publication and sidecar publication; the final verification
waited for a consistent finished pair and retained strict content-hash equality.

Final proof: [actual running cohort and restored cache](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-history-bootstrap-retry-2026-10-26/runtime-final.json).
Historical preload/cache work is complete and deployed on Demo. Future signals,
cost-policy validity and all native admission/protection checks remain required.

Entry remains intentionally blocked through an invalid latest H4. Allowing an
older EMA through that gap would be a new strategy rule and needs separate
evaluation; this cache fix does not introduce it. Broker economic parity remains
COST_INCONCLUSIVE, and no profitability/real-money/reboot qualification is added.
