# Selected26b8: did a full signal fail to become an order?

**Finding: no confirmed missed full26b8 signal in111 observed complete M15 bars.**
This does not establish complete market-data coverage. Runtime readiness is
degraded by recurring connection/permission checks, with a separate current
incomplete-H4 gate. No code/config/policy/order/service change was made.

Capture27October2026 10:23:56 Asia/Bangkok. Review existing data and journal;
no broker SDK reader, forced order or economic backtest. The smaller sufficient
approach is reconstruct causal signals and match all runtime cycles in each
90second entry window; a new trading engine or new profit optimization is not
needed to answer this question.

## Scope and integrity

- VM immutable release`selected-9cfc54a3dc78f0ae`, Rules26b8bcd69e043653.
  Complete deployed release manifest PASS;28important source/config files match
  local, including CLI omitted by the earlier10-file snapshot.
- Captured6666 completed M15 bars from the existing VM cache, SHA-bound.
  Read51828 filtered append-only audit records since25Oct17:00UTC in a single
  read-only SQLite transaction, then released it. No concurrent SDK session.
- Examined111 observed complete M15 bars closing26Oct05:30Thai through
  27Oct10:15Thai. Current exact source/config approval26Oct15:32:07Thai gives
  70eligible post-approval closes, first26Oct15:45Thai.
- Every one of those70bars has at least one current-cohort CYCLE beginning in
  its90second window. SQLite records every cycle; stdout is deduplicated.
- Canonical calculations repeated on each of111 historical prefixes to exclude
  future-bar dependence: no raw/full direction discrepancy. Recorded SIGNAL
  direction/close checked for75bar records: zero mismatches. An independent
  agent checked hashes, event uniqueness, all111prefixes,70-window coverage and
  raw/full classifications independently: PASS.

## Actual chart results

**Current cohort70bars: RAW0, FULL0.** There is no proven full signal for which
this run should already have opened a native order. Current cohort has23580
cycles and0REQUEST/0RESPONSE/0LIFECYCLE records in the captured journal.
This is bot-journal evidence, not an account-wide claim that no manual/external
deal exists. REQUEST itself also precedes a final identity check and is not fill
proof.

Across all111 observed bars, there are2RAW BUY candidates, both before the
current release approval but under the same native strategy contract:

- **26Oct14:00Thai:** close4006.459, closed-H4 EMA2004205.6868515.
- **26Oct14:30Thai:** close4007.968, same macro4205.6868515.

Both satisfy the pre-macro oscillator/trend signal but price is below macro.
Native BUY requires close>closed-H4 EMA200. Therefore both full directions0;
actual SIGNALaudit39321/39807 agrees. In each90second window a `macro_gate`
cycle is followed by duplicate-bar cycles, with some stale-quote cycles also
present. They are not full26b8 entries lost to an unrelated permission guard.

Source: [raw/full macro filtering](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/reward156_search.py:205),
[SIGNAL/bar handling](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:22).

## Real blockers, without inventing missed trades

**P1: generic connection/permission block recurs.** Current cohort records5867
`algo_permissions_required` cycles, including latest captured hours. That label
combines terminal absent/disconnected and multiple terminal/account permission
flags; these logs alone do not prove AutoTrading is simply switched off.
Such failures happen before frame/SIGNAL evaluation. An absent SIGNAL log is
therefore not evidence of an absent chart signal; offline reconstruction was
necessary. No reconstructed full signal overlapped these failures in observed
bars, so no lost profit can be attributed to them here.

Suggested minimal next fix: capture the individual flags through the existing
sender's identity read seam, distinguish reconnect from actual permission denial,
then reproduce the applicable failure before changing behavior. Do not disable
identity/permission checks or start a second reader/sender to bypass it.
Source: [identity](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/broker.py:35),
[pre-signal orchestration](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/runner.py:201).

**P2: current macro is unavailable after a partial H4.**2271 current-cohort
cycles return`macro_latest_h4_incomplete`, beginning27Oct07:00Thai through capture.
The26Oct20:00UTC H4 bucket has11/16 complete M15s. Native mapping publishes NaN
after that bucket closes and does not carry an old macro through it. Next H4
close is27Oct11:00Thai; recovery is conditional on genuinely complete/valid
input, not a promised order at11:00. No RAW signal occurred in the current
cohort even before this macro filter.

Missing M15 opens on26OctUTC:20:45,21:00,21:15,21:30,21:45, corresponding
27Oct03:45–04:45Thai. Cache alone does not establish whether this is a normal
broker break or a feed gap. Do not claim complete unseen market coverage or
invent candles. A replacement macro carry-forward rule would change native
strategy semantics and needs separate research.
Source: [closedH4](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/reward156_tuning.py:49),
[runtime macro validity](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/strategy.py:120).

**Stale-quote counts are genuine old quotes, not future-clock rejections.**3467
cycles between27Oct03:58:58 and05:00:30Thai, ages60.119658–3752.593792seconds,
all quote_rejection=stale. This overlaps the data gap. Calendar/entitlement
evidence was not newly verified here, so do not label every stale quote a code
bug or a missed eligible trade. Keeping stale quotes out of execution is correct.

**No current cooldown/cost/risk-cap blocker was observed in these cycle reasons.**
This does not prove every downstream financial gate would have passed: many
cycles return earlier, and there is no full signal to run through all later gates.

## Correction to earlier policy preparation note

The prior continuous-Demo draft said policy was loaded only once. That was
incorrect. Both deployed and local`cli.py:143–147` reload JSON every loop.
The draft has been corrected. Exact review/policy hash and expiry checks still
apply; this discovery does not mean automatic renewal exists or expiry is removed.

## Evidence and verdict

[Snapshot](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-missed-signal-audit-2026-10-27/vm-snapshot.json),
[111-bar/window Matrix](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-missed-signal-audit-2026-10-27/analysis.json),
[quote/data-gap details](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-missed-signal-audit-2026-10-27/additional-evidence.json).
Full captured audit JSON is compressed in the same run folder. All original
financial state and frozen research pins preserved.

Verdict: **fix-then-ship for unattended execution reliability**, principally
because recurring generic permission/connection failures remain unexplained.
**No confirmed missed full26b8 signal in the observed audited bars.**
