# Selected26b8 root causes before strategy tuning

Owner requirement: “tuning strategy ให้ปิดช่องโหว่ลองไล่หา root cause ทั้งหมดของตอนนี้ก่อน”.
Scope: current26b8 detector/data, broker identity/admission/lifecycle, costs/review,
daily/cooldown and watchdog. This is a bounded root-cause audit and local diagnostic
fix, not a claim that every possible future defect has been eliminated. No new
economic backtest, profitability qualification, broker send or VM change.

**Verdict: fix-then-ship for unattended execution.** The principal current
operational mechanism is repeated native MT5 Access Point handoff/reconnection.
The H4 blackout is a separate repeated native strategy/data rule. Treating either
as startup cooldown or deleting risk gates would target the wrong cause.

## 1. Confirmed proximate cause: native MT5 AP handoff loop

Native MT5 logs repeatedly show automatic switching to a reportedly better AP,
connection lost, authorization, synchronization and trading enabled again.
Across759complete disconnect intervals in the inspected native windows:

- Median handoff period16.836seconds, range16.304–17.111.
- Median disconnect→trading-enabled interval8.728seconds, range8.641–8.852.
-5850/5852 permission-blocked journal cycles in the matched log windows overlap
  these intervals. Two non-overlaps start only0.472ms/0.378ms after the logged
  enabled boundary; preserve them rather than round correlation up to100%.
- Successful identity/no_signal/duplicate cycles between failures plus repeated
  native trading-enabled messages disprove a permanently failing global trade
  flag. The native message alone is not proof of the GUI AutoTrading button.
- NTP/hostUTC are synchronized, proxy disabled, RAM/disk available and manager/
  terminal PIDs stable. No evidence of current resource exhaustion or restart
  churn explaining the loop.

**Still unknown:** why the optimizer decides to hand off repeatedly. Printed99%
quality is rounded; equal printed values do not prove equal internal scores.
AP#1 may abstract endpoints. Native/platform behavior, broker AP behavior and the
Wine/QEMU environment remain candidate deeper triggers, not proven bugs.

This is strong time-correlated proximate evidence, not a captured SDK flag for
every failed read. The existing generic `algo_permissions_required` label mixes
disconnection with several permission flags at
[BrokerView.identity](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/broker.py:36).

Minimal next operational experiment: use the prepared same-read diagnostics,
then a controlled terminal/AP comparison in a reviewed maintenance window,
preserving account/source/financial journal and collecting handoff/connected/
quote-age/entry-window metrics. Do not infer that a bot restart, host firewall
change or forced order fixes the AP optimizer. No such action occurred here.

Evidence: [native/cycle correlation](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/permissions/correlation.json),
[sanitized native logs](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/permissions/native-log-evidence.json),
[host/config facts](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/permissions/host-config-evidence.json).

## 2. Confirmed recurring mechanism: strict complete-H4 publication

M15 accepts15/15 completed M1. H4 accepts16complete M15. The26Oct20:00UTC bucket
has11/16, missing M15 opens20:45,21:00,21:15,21:30,21:45. It publishes NaN at
27Oct00:00UTC, and causal forward mapping keeps NaN until a genuinely complete
next H4 closes04:00UTC (11:00Thailand). Nothing in a later H4 may backfill an
earlier decision. Recovery at that boundary is conditional on actual complete
input; tests establish the mechanism, not a promised live order.

This repeats in the actual cache:58Mon–Thu20:00UTC buckets since16Jul,56with
11M15, one10 and one7. Post-warmup≥201H4,147RAWsignals exist and24have unavailable
macro (1BUY/23SELL). Those24 are not FULLsignals, not proved missed orders and
not lost profit. No fees/equity path has been replayed for a replacement rule.

Official [Exness instrument trading hours](https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours)
describe gold rollover closures and seasonal UTC changes. Repeated gap shape
is consistent with a regular session break, but the exact dated XAUUSDm
account-specific break is not independently attested. Do not invent candles
or relabel every missing minute a feed failure.

Root of the long macro wait is the interaction of the captured session-shaped
gap and the chosen native completeness rule, not lack of historical warmup.
Changing to last-valid-H4 carry, session-aligned H4 or another macro is a separate
research candidate. It changes which native signals can pass and must receive
its own ID and swap-inclusive matched economic evaluation.

Three new deterministic tests reproduce the real11/16 geometry, exact04:00
publication and no future backfill in
[test_c22_h4_gap_rootcause.py](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/demo/test_c22_h4_gap_rootcause.py).
[Evidence](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/h4/evidence.json).

## 3. Real observability defects, distinguished from financial policy

**Generic identity cause:** current live code loses which identity/connection/
permission field failed. This prevented direct SDK-flag attribution. Local
broker/runner diagnostics now expose only present/connected/permission booleans
and finite blocker labels, using the same existing account_info/terminal_info
reads. Existing predicates, errors and SDK call counts remain intact.

Diagnostics reset per read/cycle, never serialize account/terminal objects,
passwords or server/account values. Optional diagnostic getters cannot add a
read-only reconciliation prerequisite, and the failure explainer uses captured
safe booleans rather than re-reading fields after an original short circuit.
Required checks still fail closed if required data itself cannot be read.

**Watchdog flapping:** issue-free samples reset the incident/grace state at
[check_once](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/ops/c22_selected_watchdog.py:217).
A public synthetic6minute sequence alternating permission BLOCKED and healthy
WAIT every60seconds gives0notifications/critical=false throughout. This proves
the current reset mechanism, not that actual VM timer samples hit that exact
sequence. A future fix needs an explicit sustained/cumulative-error or stable-
recovery policy rather than inventing an alert threshold during this audit.

**Flat stale-feed blind spot:** a flat fresh-heartbeat cycle with quote24h old
is still treated as expected market-data wait without session evidence. The
existing watchdog does not prove market-open health. No stale quote is permitted
for sending by this observation; actual execution freshness gate remains strict.

**Delivery disabled:** external notifications remain owner-disabled. Local
incidents/backlog are not messages received by the owner; total VM outage cannot
be announced by an observer only on the same dead VM. No channel enabled here.

Watchdog reproductions are saved as diagnostic scripts/results rather than
permanent tests approving those weaknesses:
[watchdog-witness-results.json](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/policy/watchdog-witness-results.json).

## 4. Confirmed future/conditional hard blocks

- **168h cost expiry:** current1Nov20:25:18Thailand expiry remains. Accepted
  original review survives restart but does not renew policy age. Calendar
  completeness and actual-cost drift are independent checks.
- **Review-policy coupling:** CLI actually reloads JSON every loop. A refreshed
  policy without matching exact review binding still fails; a timestamp-only
  renewal is not evidence. Review combines many causes into one generic reason
  before signal evaluation, so later blockers may remain masked.
- **Remaining daily risk:** removing a missing-calendar blocker can reveal a
  daily-loss blocker next. New public-cycle test demonstrates calendar→daily
  threshold with same baseline200, no order_check/send and no reset.
- **Latched halt after UNKNOWN:** delayed broker proof can resolve an ambiguous
  request to CLOSED while safety_halt remains. A fresh post-cooldown signal after
  restart is still blocked; it is not a timer that should clear automatically.
- **Held-midnight baseline:** current first1second proof window can fail when
  SDK reads are slow. No evidence it blocked the observed no-position cohort;
  do not reconstruct held floating equity from restart/current equity.

Three new public-seam tests cover restart/expiry, stacked calendar/daily gates,
and UNKNOWN→proven CLOSED→restart with persisted halt in
[test_c22_rootcause_policy_interactions.py](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/demo/test_c22_rootcause_policy_interactions.py).
These preserve policies; they are not automatic-renewal or halt-reset features.

## 5. Expected native strategy behavior, not repaired as bugs

Native30minute post-loss cooldown already resumes conditionally. UTC loss2 and
daily limits reset/evaluate under their existing rules. Fixed0.01/risk10% stays.
Daily10% is an entry threshold, not reserved next-SL liability; native runtime
has no live DD40% breaker or24hDD auto-resume overlay. Prior risk-closure study
did not select a replacement meeting the owner's matched profit/risk goal.

The earlier missed-signal audit found0FULLsignals in111observed complete bars,
including70current-cohort bars. Two earlier RAW BUYs were belowH4EMA200. Thus
neither the AP loop nor a newly available macro justifies an invented entry or
profit claim. Data gaps remain explicitly outside full coverage proof.

## Local test/implementation outcome

Broad Research→Plan→Implement records appended to existing.testagent files;
generator/pairing/gap/quality tool capabilities were unavailable, so bounded
manual pairing and independent review used. Earlier metadata/dirty work retained.

- New identity diagnostics tests cover disconnected recovery/no resend,
  everypermission denial, wrong/real/missingidentity, reset after SDK exception,
  active read-only close, requireddisconnection, optional getter exceptions,
  unknown flags and capital/journal failures without leaking values.
- Behavioral RED artifacts retained for missing diagnostics and optional getter
  regressions introduced during diagnostic implementation. They do not claim the
  AP reconnect defect was fixed. Independent review found the short-circuit
  explainer issue; it was reproduced and fixed before final validation.
-16new focused tests PASS; independent code/assertion review has no remaining
  actionable finding in the diagnostic delta. Full-suite result recorded below
  after clean completion; no coverage-percentage claim without measurement.
-101frozen campaign source pins match. Native selectedconfig/strategy/adapter
  files match the pre-task snapshot. Only shared broker/runner diagnostic code
  plus three new test files and documentation are task changes.

**Not deployed:** local diagnostics create a different future runtime release
hash. The existing VM release, policy expiry, account, order journal, services,
permission gates and financial behavior were not changed. No claim of root
AP-trigger resolution, improved economic return or fresh broker cost attestation.

Artifacts: [run folder](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27),
[local diagnostic delta](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/local-diagnostic.diff),
[preservation](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/preservation.json).


## Final clean validation and unchanged VM

- `PYTHONPATH=. .venv/bin/python -m unittest tests.demo.test_c22_identity_diagnostics tests.demo.test_c22_h4_gap_rootcause tests.demo.test_c22_rootcause_policy_interactions`:16tests,20.628s,OK.
- `.venv/bin/python -m unittest discover -s tests`:1279tests,195.078s,OK(skipped=2),exit0. ExpectednegativeCLIusage/dry-runmessagesinlogaretestfixtures,notnewbroker/economicruns.
- ScopedRuffcheck andpy_compilePASS. `.venv/bin/python -m ruff`wasunavailable; installed`ruff`CLIusedsuccessfully,no dependencychange. No measuredcoverage/typecheckerclaim.
- Finalread-onlyVMcapture27Oct10:57:15Thailand:oldbroker/runner/CLI/confighashesmatchpre-taskbaseline;execution/terminalactive,execute=true. LatestcycleBLOCKED/algo_permissions_required;cachedmacroNaN,nextH4close11:00conditional. Noactiveintent/safetyhaltinreadjournal;lastpositionsreadunknown,notafreshbroker-flatproof.
- [validation.json](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/validation.json), [final-vm.json](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/final-vm.json).


## Live boundary confirmation —27Oct11:00:52Thailand

At11:00:03.722Thailand the originalVMrunner read16/16M15, completeH4366 and
macro4196.36059702943; resultWAIT/no_signal. Cache grew6668→6669 and retained
history_seed_statusrestored. ExecutionPID52912/terminalPID34838 andNRestarts0
unchanged: genuineH4availability recovered withoutrestart/reseed/configchange.
Latercapturedcycle11:00:51againblockedalgo_permissions_required withthefinite
macroretained. This directlyseparatesresolvedH4waitfromongoingAP/identityproblem.
Noinferredorder: boundarycyclehadnoeligible26b8signal. Latestpositionsreadunknown,
notaccount-wideflatproof.

[Livepost-boundarycycles](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/h4/live-boundary-after.json).
