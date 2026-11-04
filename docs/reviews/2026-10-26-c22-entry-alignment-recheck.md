# Selected26b8 entry-condition alignment recheck

Read-only follow-up to the history/cache fix. Goal: verify that current graph
inputs, native signal rules, admission, money management and execution permission
work together, and distinguish intended rejection from an implementation defect.
The smallest useful action is to inspect the existing sender and reproduce its
decision path; another strategy engine, forced order or economic backtest is
unnecessary for this question.

**Verdict: native26b8 signal/geometry and declared admission rules align. One P2
quote-observation clock defect needs a focused fix. Existing daily/DD/swap limits
must not be interpreted as stronger guarantees than the implementation provides.**
No runtime source, config, policy, service, permission or order was changed.

Follow-up: the owner subsequently authorized repair. The quote-clock and related
post-read admission-window corrections were deployed to Demo26October2026
15:32Asia/Bangkok with native config unchanged. Closure/test/deployment scope is
recorded in [quote clock fix](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-10-26-c22-quote-clock-fix.md).
The financial-policy gaps below remain separate next-version design work.

## Verified running source and actual decisions

VM snapshot26October2026 14:19:16Asia/Bangkok: execution is active,execute=true,
PID49393,release selected-98c2c73ed40ae408,0 restarts. The dedicated terminal is
active and competing selected/legacy senders/shadows are inactive. All80 release
files pass their manifest hashes; comparable local sources/config match. Current
owner review passes the actual ExecutionReview.check using its exact captured
raw-byte digest, current policy and source cohort, with a get-only journal.

The static config default_mode=shadow and policy execution_authorized=false do
not contradict actual Demo sending. The entrypoint explicitly requires --execute
and a source-bound owner review; SELECTED_DEMO_ARMED_TRIAL separately authorizes
the limited Demo trial. The false inner-artifact qualification fields are checked
as part of that contract. Sources:
[entrypoint](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/__main__.py:42),
[armed permission](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/execution.py:49).

The captured CSV contains6,591 complete BidM15 bars and361 complete H4. Independently
spelled predicates match native raw/final direction,ATR,EMA50 and closed-H4 EMA
over the whole prefix:0 mismatches,indicator tolerance1e-10. Four actual
current-cohort SIGNAL records also match their input rows:

- 13:30BKK: no_signal; RSI7 remains above30 rather than crossing upward from below.
- 13:45BKK: no_signal; RSI7 falls32.7385→26.2933.
- 14:00BKK: macro_gate; RSI7 rises26.2933→30.2098,close4006.459 is above rising
  EMA50 4004.7676, but below closed-H4 EMA200 4205.6869. The BUY is intentionally
  rejected against the larger trend.
- 14:15BKK: no_signal; RSI7 falls30.2098→23.5724.

BUY requires RSI7 cross30, positive close change, close above rising EMA50 and
above closed-H4 EMA200. SELL requires close below prior48-low, below falling
EMA50 and below closed-H4 EMA200. BUY/SELL cannot simultaneously pass their
opposite EMA50 predicates. SL2.5ATR on both sides, BUY TP3R,SELL TP1.35R and BE1R
agree with the selected recipe. Sources:
[native detectors](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/campaign_signals.py:57),
[macro gate](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/reward156_search.py:205),
[contract](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/strategy.py:27),
[entry geometry](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/breakout_entry.py:28).

## P2: a fresh quote can fail against the cycle-start clock

The runner reads identity, exposure, history and symbol specifications before
calling broker._quote(now), but now still represents cycle start. The SDK tick can
be newer than that timestamp while already being in the past by the time the SDK
returns. The validator then reports quote_stale for a negative computed age.
Sources: [caller](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/runner.py:222),
[strict age check](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/broker.py:179).

Deterministic witness: cycle starts at0ms,tick at200ms,SDK response observed at250ms.
Current age=-200ms produces rejection; actual observed age=50ms passes. The public
SelectedDemoRunner.cycle differential changes only the validation comparison clock
in the test environment: BLOCKED/quote_stale becomes SHADOW_ADMIT,with0 order sends
in both paths. A quote genuinely in the future relative to observation still
fails. This is an API/control-flow witness, not a trading result.

Minimal proposed fix: compare quote freshness with a verified post-read observed
UTC clock, derived without changing the canonical signal/day clock. Keep the
60second maximum age, actual-future rejection, UTC checks and price validation.
Refreshing time only before symbol_info_tick still leaves its call latency out.
The same seam is used by pre-send and management checks. Add tick timestamp,
cycle/observation timestamps and computed age to rejection evidence so future
versus old-price failures can be distinguished. No guard should be loosened to
force entry.

In the captured866 current-release cycles,28 report quote_stale,about3.23% of
cycles,not3.23% of time or missed trades. They do not record the rejected tick
timestamp/age,so they cannot be attributed to this defect. All four eligible new
M15 decisions in the captured window were evaluated,5.68–9.90seconds after close,
inside the90second entry window. No missed qualifying trade is established.

## Money management aligns with the contract, with narrower guarantees

Fixed0.01 lot,10% initial equity-risk cap, broker profit/margin checks, stop/freeze
geometry and fresh pre-send equity/exposure rechecks align. Risk calculations
include declared commission and slippage; oversized fixed lots are rejected.
Two negative completed owned positions stop subsequent entries on the UTC day;
each negative net exit starts30 elapsed minutes cooldown. Net includes actual
swap/fees,so a nominal BE exit can correctly trigger these guards. Cooldown does
not block owned BE management. Sources:
[admission and risk](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:49),
[pre-send checks](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:150),
[owned loss count](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:206),
[cooldown](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/runner.py:30).

Three existing gaps against stronger outcome expectations remain:

- Daily10% is an observed-equity entry stop,not a reserved SL budget or forced
  close. At day baseline200/equity182,a further modeled risk18.101 can pass the
  current rules and exceed10% total daily loss if realized. This synthetic
  witness is already recorded in the prior rule review; it is not an observed
  VM loss or new backtest. A remaining-budget guard would be a new policy.
- DD≤40% was a research selection gate. The current static contract contains no
  live portfolio-equity DD40% breaker. Historical passing DD cannot enforce it
  during future execution. A live breaker needs a defined equity peak,cashflow
  treatment,observation and resume policy.
- Initial10% risk and the BE trigger/stop omit additional holding swap. BE does
  not guarantee nonnegative final net after rollover. A swap reserve or net-BE
  change would alter admission/exits and needs a separate swap-inclusive replay.

Sources: [daily admission](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:71),
[static selected contract](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/strategy.py:27),
[BE money calculation](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/lifecycle.py:204).
Existing isolated options and their trade-offs are retained in
[risk options](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-10-26-c22-26b8-risk-options.md).

## Other intended gates and labels

- Cost policy v2 validates against its captured spec/account/calendar at the
  snapshot. Its168hour lifetime ends1November2026 20:25:18Asia/Bangkok; afterward
  entries block until fresh evidence/review exists. There is no automatic renewal.
  Actual swap/spec drift can block earlier. This audit creates no cost attestation.
  [Policy lifetime](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/costs.py:31).
- 90seconds after M15 close, a provable first quote,0.10price-unit allowed change
  before send and fresh margin/exposure checks have separate roles. A changed
  executable quote can reject/retry within the window; signal detection success
  alone does not authorize order_send.
  [Admission](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:55).
- Runtime requires201 complete H4 while canonical EMA200 becomes finite at200.
  A synthetic200-H4 SELL is blocked by the stricter runtime startup guard. This
  is documented conservatism,not the current blocker because361 are available.
  [Startup guard](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/strategy.py:128),
  [macro minimum](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/reward156_tuning.py:61).
- entry_ready=true is emitted only for SHADOW_ADMIT. A false value alone does
  not mean the armed Demo sender is disabled; use execute,reason,review/cohort and
  actual lifecycle state together.
  [Status construction](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/runner.py:138).
- Missing held-midnight equity proof blocks new admission,while active/UNKNOWN
  protection continues. Ambiguous submitted orders remain UNKNOWN and are never
  blindly resent. Owned complete exits reconcile before new-entry history,
  review and quote gates. The quote clock defect can still delay other protection
  checks until a later cycle; this audit does not imply uninterrupted management.
  [Cycle ordering](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/runner.py:198),
  [persist before send](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:192).

## Verification and scope

Native signal suite17tests/12.709seconds:OK. Risk/execution/armed-trial/lifecycle/
containment suite65tests/82.358seconds:OK. These are existing focused suites; the
new deterministic quote witness reveals a case they did not cover. Full repository
suite was not rerun for this read-only review. Prior1227-test history-fix validation
is separate evidence. No new economic backtest,parameter search,broker SDK reader,
forced order or profit claim was introduced. Current-cohort native order execution
is not demonstrated by these four rejected/no-signal decisions; the prior manual
open/close smoke proves a different,narrower execution path.

Machine evidence under
[run folder](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-entry-alignment-recheck-2026-10-26):
[actual VM source/status](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-entry-alignment-recheck-2026-10-26/vm-status.json),
[native signal comparison](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-entry-alignment-recheck-2026-10-26/native-signal-audit.json),
[exact owner-review check](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-entry-alignment-recheck-2026-10-26/execution-review-audit.json),
[clock witness and policy expiry](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-entry-alignment-recheck-2026-10-26/risk-time-witness.json).

Recommended order: fix/test the quote observation clock without changing native
signals; then evaluate any desired stronger daily/DD/net-BE policies as isolated
research versions. Do not remove macro,cooldown,cost or risk gates merely to get
an order. **Fix-then-ship for the clock repair; retain the frozen26b8 recipe.**
