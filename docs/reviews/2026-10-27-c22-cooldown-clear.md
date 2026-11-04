# Selected26b8: startup readiness versus post-loss cooldown

Owner clarification: wants the bot to run and enter eligible orders without
getting stuck in cooldown/waits. Read-only VM capture at27October2026 00:42:24
Asia/Bangkok. No runtime, policy, journal or order mutation performed.

## Actual current state

Execution active, execute=true, same native26b8 Rules, flat journal, no active
intent or safety_halt, no persisted selected_last_loss_ms in the captured keys.
Ten important deployed source/config files match local copies. Sender and
terminal remain the existing single-sender pair. No concurrent broker SDK probe.

Latest result WAIT/duplicate_bar means that closed bar has already been handled;
it is not a30minute startup wait. The captured6629+ causal prefix now contains
6632 completed M15 bars. Canonical evaluation of the last8 bars, closing
26Oct22:45 through27Oct00:30 Thailand, gives direction0 and raw_direction0 for
every bar. Therefore clearing a cooldown would not make any of those8 signals
an order. This is a cache reconstruction, not a fresh broker fill guarantee.

The existing approval/restart and restored history permit future eligible native
entries without another48hour soak or201 new H4 accumulation. Initial fresh M15
after approval has long passed. The current cycle is not returning cooldown.
Normal signal/data/risk/account/cost gates still apply at a future entry.

## The30minute rule is a strategy rule

`scripts/c22_selected/runner.py:30` compares a signal's first quote with the last
completed owned negative-net exit plus30 elapsed minutes. It is not a timer
started whenever the bot process starts. It survives restart and UTC midnight;
the bot automatically considers later fresh signals after the interval. Clearing
financial state to remove this timer would discard evidence and is unnecessary.

## Exact historical removal comparison already exists

The frozen exhaustive catalog includes `46122e367f419739`, differing from native
`26b8bcd69e043653` only in cooldown_bars2→0. Same signals/fixed0.01/risk/daily
loss/SL/TP/BE. Initial$200,1Sep2024 through24Oct2026 exclusive, modeled swap in
all views; no new economic replay performed.

- Base raw/cent net: native+$1,945.334; cooldown0+$1,613.7434. Decrease$331.5906,
  approximately17.05%. Base trade count460 for both, DD34.2750%→35.3404%.
- Stress raw net$1,471.870→$1,181.8886; cent$1,471.870→$1,235.1562.
- Fee raw net$1,464.592→$1,175.0286; cent$1,416.994→$1,175.0286.
- Worst six-view DD38.6710%→39.8235%; raw-net loss streak11→12.
- Base cooldown rejections12→0, but altered admission/equity/holding/day paths
  produce different trades rather than adding12 certain winners. Busy/daily
  gates still exist. No claim that removing this timer removes every blocker.

The exhaustive independent audit covers all5184profiles,15552raw and174required
cent cells. Agent verified zero variant's six payload/proof hashes against that
audit and its pinned ancestry. Selected fresh repeats and separately reconstructed
independent full-tick DD are for the native winner, not a new dedicated independent
full-tick reconstruction of cooldown0. COST_INCONCLUSIVE and exposed-history
selection limits remain.

## Verdict

No current cooldown latch was found to clear; the latest8 bars have no native
signal. Keep current sender running and preserve its journal. Removing native
post-loss cooldown is a changed strategy with worse matched historical profit
and risk in this comparison, not a demonstrated startup fix. A deliberate Demo
switch to cooldown0 would need its distinct Rules/config identity, adapter/test
and source-bound execution review; it must not masquerade as unchanged26b8.

Machine evidence:
[VM](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-cooldown-clear-2026-10-27/vm-snapshot.json),
[last8 native bars](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-cooldown-clear-2026-10-27/current-admission-evidence.json),
[six-view comparison](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-cooldown-clear-2026-10-27/cooldown-comparison.json).
Original catalog/results/audit remain under`runs/c22-exhaustive-loop-2026-10-25/`.
