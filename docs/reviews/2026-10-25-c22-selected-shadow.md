# Selected26b8 bot test: Oracle shadow running

Owner selected `26b8bcd69e043653` for bot testing. New snapshot
`RESEARCH-C22-SELECTED-20261025-26B8` is running as
`c22-selected-shadow.service` on the existing Oracle VM. Sending stays off;
this is runtime observation, not a qualified forward return or Demo execution.

## Contract and implementation

New isolated `scripts/c22_selected` preserves the original detector/source pins
and C22 rollback contract. All28 native Rules match selected26b8: archived
RSI7cross30 BUY/EMA50, SELL48/EMA50, closed H4EMA200; BUY SL2.5ATR/TP3R,
SELL SL2.5ATR/TP1.35R, both BE1R at completed-bar first quote. Fixed0.01,
cost-inclusive10% cap,daily10%/two negative completed exits.30elapsed-minute
negative-net cooldown includes swap/commission/fee and crosses UTC/restart;
compares first quote time,consumes ineligible bars,never delays protection.

Shared broker lifecycle/cost/identity/persistence remain unchanged. Separate
config/journal/magic22261025 and selected release/cohort hashes prevent mixing
strategies. CLI forces shadow regardless of inherited send environment. No
parameter was retuned to clear operational admission.

## Verification

| Requirement | Evidence |
| --- | --- |
| Native identity/signals | `test_cache_uses_complete_selected_native_rules`, `test_both_signal_directions_match_frozen_research_seed` |
| Rounded geometry/cap | `test_rounded_buy_sell_geometry_and_cost_inclusive_cap`, hand-calculated expected values |
| BE/lifecycle | `test_buy_and_sell_move_be_only_after_a_new_closed_bar`, `test_ambiguous_selected_send_remains_unknown_after_restart` |
| Cooldown/daily2/UTC/restart | `test_cooldown_compares_first_quote_not_later_poll_and_consumes_bar`, `test_exact_elapsed_cooldown_boundary_admits_after_restart`, `test_negative_swap_cooldown_survives_utc_day_reset`, `test_two_net_losses_block_new_entry` |
| Shadow/no sends | `test_shadow_selected_sell_has_native_target_and_never_sends`, `test_send_mode_rejected_before_broker_initialization` |
| Bounded deterministic release | `test_archive_is_deterministic_shadow_only_and_exclusive` |
| Actual archive agreement |49,729 bars,469BUY/504SELL signals,9detector columns matched;2,751 entry geometries across6 raw/cent×base/stress/fee paths,1,595BUY/1,156SELL,0mismatches |
| Regression |22selected tests PASS;full1,118tests PASS,skipped2;Pyright0errors;Ruff PASS |

Parity shares canonical detector/entry helpers: not an independent algorithm
or complete lifecycle/broker fill qualification. Tape is memory-mapped only at
entry timestamps,not rescanned or economically replayed. All economic reference
paths include modeled swap. Initial failed parity artifact is kept: comparison
first widened Ask by the whole stress spread; fixed the comparison to canonical
Bid−half/Ask+half. Runtime strategy geometry was not changed to conceal it.

## Standards and spec review

Two read-only agents reviewed the scoped changes against repository standards
and `specs/c22-selected-demo-adapter-2026-10-25.md`: no unresolved material
finding on either axis. Root review found the release unit test depended on
an ignored old-run manifest; replaced that dependency with a synthetic temporary
repository/allowlist/config fixture. The runtime and deployed release did not
change. Focused release regression and Ruff pass after that test-only repair.

## Actual Oracle handoff

Release `/home/ubuntu/c22-demo/releases/selected-e983cf8ce143b5f4`.
Archive SHA256:
`ce5441b51f90a4a605b1b2849c9995fd8a100581912a434800d80d54c6b9ebe2`.
66file bindings verified on VM;existing58runtime files have no differences from
original deployed manifest. No credentials,journals or raw research runs bundled.
All101 frozen research pins remain unchanged.

Fresh unit/journal inspection confirmed oldshadow execute=false/no active
position and executioninactive. Consistent oldjournal backup downloaded/restored
onMac with SHA/SQLite integrity/count checks;its1pending outbox item retained.
Only then oldshadow stopped. Exclusive read-only MT5 probe at
2026-10-25T11:55:14Z confirmed expected USD hedging Demo identity,zero positions/
orders and AutoTrading=false. No order API was invoked by this handoff.

New gate0 observer runs with its own journal/cache and shared account writer
lock. Newshadow enabledforboot;oldobserver disabled/inactive;executioninactive.
The oldcurrent pointer/release remain for rollback. Notification variables
explicitly unset;no messages sent. At2026-10-25T11:59:01Z a fresh newcycle showed
correctsnapshot,execute=false,flat/zero observed positions and BLOCKEDquote_stale
while market closed. Initial transient connection/permission blocks are retained.
Bootstrap history is not counted as prospective qualification.

Newjournal backup also downloaded/restored onMac. Its snapshot has0order REQUEST
audit events;all CYCLE records use one selected source/config cohort. One shared
constructor STATE record predates selected-release augmentation;it is initialization
metadata,not a trade observation. New/old backup hashes and tablecounts retained.

Final read-only check at2026-10-25T12:09:37Z confirmed running/MainPID26434,
zero restarts, latest cycle age0.215s, execute=false,flat/zero observed positions,
zero REQUEST events,send gate0 and notification variables absent. Evidence in
`runtime-final.json`;aggregate checks in `delivery-checks.json`.

Machine artifacts in ignored `runs/c22-selected-demo-2026-10-25/`: final archive
parity,release-final build,flat-probe,handoff,testlogs,old/newSQLite backups and
Mac restore proofs. No order was sent,modified or closed in this task.

## Remaining gates

VM cost policy remains COST_INCONCLUSIVE with no reviewed_utc. Fresh supported
tariff/spec/calendar/account review,newcandidate feed/parity and genuinely new
shadow observations remain required. Old Monday waiver/feed review do not
transfer. Forward sample/review endpoints remain undecided;no economic cohort
is frozen. Actual Demo order sending and real money remain off.

Existing automatic backup service still targets oldjournal;newjournal has
verified manual Mac snapshots,not unattended backup/monitor qualification.
Unattended execution needs its separate operational review. Historical DD40%
is not a guaranteed future maximum. The observer waits for fresh market data
and reports blockers rather than bypassing them.

Termius read-only log command:

```bash
sudo journalctl -u c22-selected-shadow.service -f
```
