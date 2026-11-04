# Selected26b8 execution review: lifecycle and unattended operation

Scope: review the actual Selected26b8 Demo sender, from the Wine entrypoint
through shared admission, broker reads, persisted lifecycle and deployed units.
The goal is reliable execution of the already selected rules on actual Demo
signals. The smallest solution is to repair the existing shared lifecycle and
operational seams; another strategy engine or a strategy retune is unnecessary
for these findings. This review changes no strategy, source pin, order, service,
permission, cost policy or financial journal.

## Verified runtime and validation

Read-only VM observations at 2026-10-25T16:57:07Z confirm execution active with
PID31184, zero restarts, terminal active, and shadow inactive. SHA256 of all six
examined runtime/entrypoint files exactly matches the local files used below.
At 16:58:07Z (23:58 Asia/Bangkok), the persisted cycle is execute=true,
BLOCKED/quote_stale, flat, with no active intent, no safety halt and no pending
outbox. There are 12,129 retained CYCLE events and no REQUEST event. This does
not demonstrate a future broker fill.

Current focused suite: 75 tests PASS in 55.730s:

```bash
PYTHONPATH=. .venv/bin/python -m unittest \
  tests.demo.test_c22_selected_runner \
  tests.demo.test_c22_selected_armed_trial \
  tests.demo.test_trial30_demo \
  tests.demo.test_c22h4_trade_log \
  tests.demo.test_demo_containment
```

Four additional counterexamples ran through public SelectedDemoRunner.cycle,
including the armed trial review wrapper, real SQLite state and the existing
broker boundary fixtures. All four assertions reproduced the behavior described
below. They are software/accounting regressions, not new economic backtests or
real broker responses. No actual MT5 SDK session or order was opened for them.
Postman HTTP simulation does not exercise this native MT5 boundary; existing
native broker fixtures are the relevant verification seam here.

## 1. P1 operational gap: reboot does not restore the selected manager

Evidence: actual execution UnitFileState=static, terminal UnitFileState=transient
with its unit under /run/systemd/transient, while selected shadow remains
enabled for boot. The execution unit has no terminal dependency or installation
section. A reboot therefore does not restore the reviewed execution/terminal
pair. The old shadow uses a different journal and is not recovery of an owned
execution intent. Broker-held SL/TP are distinct from the bot's BE/reconciliation
manager.

This limitation was already disclosed in
`docs/reviews/2026-10-25-c22-monday-armed-demo.md:100`; it is not a newly observed
crash. It becomes material when the requirement is unattended operation.

Suggested change: persistent dedicated terminal plus a single selected manager
boot path, ordered startup, account/source checks and recovery from the existing
execution journal. Remove the competing shadow boot path as part of the same
reviewed switch. Test restart/reboot with persisted FILLED and UNKNOWN fixture
states and prove no resend. Retain flat rollback; do not stop an owned manager
casually. No boot or service change was made in this review.

## 2. P2 code finding: BE treats PLACED as rejection and resubmits SL/TP

Location: `scripts/demo_runtime/lifecycle.py:254-260`.

The BE path persists be_pending before send, then clears it for retcode10008
because its accepted/ambiguous set includes only10009/10012/10031. The official
[MT5 return-code contract](https://www.mql5.com/en/docs/constants/errorswarnings/enum_trade_return_codes)
defines10008 as PLACED. Entry and safety-close paths already retain10008.

Counterexample: fill selected SELL, reach BE on a new completed M15, then return
10008 without reflecting the changed SL yet. Two consecutive public cycles both
report MANAGING/be_rejected, pending is removed, and request actions become
[DEAL, SLTP, SLTP]. This proves duplicate modification requests under that
response; it does not prove a duplicate entry or that this broker has returned
10008 for SLTP in practice.

Suggested change: preserve pending for an accepted/ambiguous BE response,
reconcile actual broker SL before BE_MOVED, and never resend while unresolved.
Add both-side delayed-confirmation and restart coverage for10008. Use named
retcode handling consistently across the existing lifecycle.

## 3. P2 code finding: entry prerequisites block read-only close reconciliation

Location: `scripts/demo_runtime/runner.py:201-206` and
`scripts/demo_runtime/broker.py:163-180`.

The runner demands trading permission, a fully tradable symbol and a fresh
quote before checking whether an active intent needs reconciliation. A complete
closed position ledger requires none of those mutation prerequisites.

Counterexample A: broker has no position and a complete owned exit deal, but the
last quote is over60seconds old. The runner returns BLOCKED/quote_stale, retains
active and later emits critical=true despite observed_positions=0. No CLOSED
event is produced while that quote remains stale. Counterexample B: the same
confirmed close with AutoTrading disabled is blocked even before reading
exposure/history. Existing broker SL/TP were not removed by these scenarios.

Suggested change: retain strict Demo identity and fresh complete exposure/deal
reads, reconcile a proven closed ledger first, then require tradability, current
quotes and trade permissions only for admission or a broker mutation. Every
send/modify/close boundary must retain its current strict checks. Do not infer
flat from an absent quote or incomplete history.

## 4. P2 availability gap: held-midnight baseline has only a one-second capture window

Location: `scripts/demo_runtime/broker.py:128-149`,
`scripts/demo_runtime/runner.py:219-222` and
`scripts/demo_runtime/admission.py:39`.

If a position existed at00:00UTC and no daily baseline was persisted during its
first second, later baseline construction raises day_start_floating_unknown.
Active management intentionally ignores that error; after the position closes,
new admission is blocked for the remaining UTC day. Public-cycle reproduction
at00:00:30.500 followed by close and the next completed bar demonstrates this.
The CLOSED result also reports the retained prior-day day_start value, so a
consumer must not interpret it as a proved current-day baseline.

This is an intentional fail-closed guard already covered by
`tests/demo/test_demo_containment.py:269`, not a reason to remove daily risk
protection. The missing capability is reliable evidence collection at rollover.
The deployed CLI polls after a one-second sleep plus work and only prints
unchanged results about every60seconds (`scripts/demo_runtime/cli.py:40,154,161`).
Log spacing alone does not measure polling frequency. Work, SDK latency or a
restart can still miss the one-second capture window.

Suggested change: design and persist an independently verifiable UTC-boundary
equity mark or reconstruct it from complete timestamped position/deal/quote and
cost evidence. Keep blocking when reconstruction cannot be proved. Never latch
current equity later as a replacement or widen the daily allowance silently.
Expose baseline day/source/validity in closure diagnostics rather than presenting
an old baseline without its date. Baseline semantics must remain explicit when
implementing this change.

## 5. P2 operational gap: no external failure or protection notification

Evidence: deployed execution unit explicitly unsets DEMO_TELEGRAM_TOKEN,
DEMO_TELEGRAM_CHAT_ID and DEMO_HEALTHCHECK_URL; runtime environment names are
absent. CRITICAL and lifecycle evidence persist locally, but an owner who is not
following journalctl receives no verified external alert. Local process restart
does not detect all stopped/blocked/UNKNOWN conditions from outside that process.
This was also previously disclosed, not an observed delivery failure.

Suggested change: configure an owner-approved private health/failure channel,
verify delivery/retry and stale-heartbeat detection, and make broker-confirmed
FILLED/CLOSED/BE events distinguishable from BLOCKED/UNKNOWN. Keep notification
content account-safe. No external message was sent in this review.

## Remaining constraints and verdict

Regular-swap Demo assumptions and exact observed-cost drift blocking remain
unchanged. The policy expires2026-11-01T13:25:18Z; renewal needs new evidence and
a matching review, not timestamp editing. Swap-Free entitlement and broker-feed
economic parity remain unproved. This review neither reruns profitability nor
claims DD40% is a forward guarantee. Actual broker fill, price/cost accounting
and BE confirmation still need evidence from an eligible future signal.

Verdict: **fix-then-ship for unattended operation**. Preserve Selected26b8 rules
and repair lifecycle/recovery first. Two reproduced code findings, one deliberate
fail-closed availability limitation and two known operational gaps prevent an
unqualified unattended-readiness claim. The Demo sender remains untouched.

Evidence under ignored `runs/c22-scrutinize-2026-10-25/`: `vm-audit.json`,
`vm-source-check.json`, `vm-status-latest.json`, `reproduce.py`,
`counterexamples.json`. Reproduce offline with:

```bash
PYTHONPATH=. .venv/bin/python runs/c22-scrutinize-2026-10-25/reproduce.py
```
