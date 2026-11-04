# C22H4 research Demo replacement

Implementation available; broker parity/shadow/cutover **pending**. Real money PROHIBITED. Same Demo account replaces trial30; never simultaneous runners. `make bot-*` now selects C22H4; explicit `make trial30-*` targets retain rollback. Research returns do not qualify profitability or broker costs.

Owner reaffirmed C22H4 as the new Demo strategy on 2026-10-04 and requested default runner replacement. Keep frozen `1af968e9ac6a26ea` contract unchanged while resolving readiness findings in [PR scrutiny](../reviews/2026-10-04-c22h4-pr-scrutinize.md). Current local correction2026-10-23: `bot-run`/`bot-start` always force shadow even when the inherited execution gate is1. Sending uses `bot-execute`/`c22h4-run`; rollback sending uses `trial30-execute`. Baseline is now account/UTC-day bound and restart-persistent. Legacy `restart_equity` values cannot authorize entries. Candidate PID/log paths are `data/c22h4-demo-watch.pid` and `data/c22h4-demo-watch.log`; exact cache is `data/c22h4-shadow-bars.csv`. PR merge and broker cutover are separate actions.

## Contract

`config/c22h4-demo.json`: snapshot `RESEARCH-C22-H4EMA200-20261004`, config ID `1af968e9ac6a26ea`, exact source hashes. Canonical contract/math in CORE_STRATEGY section6.33. Fixed0.01, risk10%, daily10%, one losing completed exit per UTC day, BUY protection off, SELL BE1R. Default candidate journal separate from trial30; same-account local writer guard shared across both CLI paths, including journal overrides. Old pre-upgrade watchers must be stopped: they do not hold this new guard.

## Read-only history and parity gate

Confirm trial30 watcher stopped or arrange exclusive terminal probe access before starting another MT5 Python client. Do not change cost policy for history probe; no journals/order APIs opened.

```bash
make c22h4-history-probe
```

Writes `data/c22h4-history-probe/{probe.json,broker-bars.csv,parity.csv,admissions.csv,decision-divergences.csv}`. Broker Bid M1 -> complete M15, >=201 complete H4, bootstrap <60 seconds. Detector replay keeps each feed's full causal prefix; overlap ends <=2026-10-02. Per-signal direction plus modeled admission/risk geometry use common archive-close quote, Ask=Bid+0.2, slippage0.1, fee0, equity200. These shared hypotheses isolate feed/indicator differences; they do not establish historical execution costs or actual quote parity. Review every divergent signal/admission and ATR/macro/level difference; missing bars and OHLC/prior-prefix differences are listed, not automatically accepted. Empty or un-warmed signal evidence cannot pass. Source/input/output hashes and explicit geometry/indicator divergence counters recorded. Matching evidence is labeled `match`. Terminal depth exploration queries up to800000 M1 within60seconds; deepest successful response reports contiguous M1 and complete M15/H4. A query ceiling is not proof of unrestricted terminal history. Probe exit0 only if history and admission/direction gates pass; owner review still required for explanations and maximum-history depth.

Initial run from Codex sandbox failed before MT5 initialization: `wine: cannot find the server port: 0x0000044c`. Depth/latency/parity unverified. No archive seed or disk warmup fallback selected; if deep history fails, owner chooses plan fallback before execution.

## Shadow and exact cache audit

Owner re-attests the explicit cost-policy file using existing tariff/account evidence workflow in [trial30-demo.md](trial30-demo.md). Do not merely change timestamp to bypass validation. Shadow performs broker `order_check`, never `order_send` or phantom fill notifications.

```bash
make c22h4-once
make c22h4-shadow > data/c22h4-shadow.log 2>&1
```

Foreground watcher, Ctrl-C stops. Cache bootstraps once from 100000 M1 copied in 50000-bar pages; a single 100000 request is rejected when MaxBars is 100000. Updates from 5000-M1 tail per completed M15; only new bar runs full research detector. `data/c22h4-shadow-bars.csv` atomically stores exact causal prefix for offline `prepare_candidate` replay; output contains non-null `macro_ema` and cache size, durable journal includes same diagnostics. Cache divergence blocks then rebuilds; **any divergence fails this shadow gate**. `--cache-output` supports explicit alternative local evidence path.

Collect >=48 hours and >=96 completed M15 bars spanning >=1 UTC midnight, no unexpected BLOCKED status, non-null macro, no cache divergence. Replay signal/WAIT reason on exact exported bars with frozen contract; duplicate-bar WAIT and expired entry windows must be distinguished. Shadow is plumbing evidence; signal frequency (~one per five days) means no observed signal alone proves nothing. Initial offline parity remains independent gate.

## Cutover: owner approval at execution time

Current attended-trial procedure and owner-approved operating scope:
[attended market-open trial](c22-attended-market-open.md). It supersedes the
earlier mandatory Telegram/private-bucket requirements only for a trial with
an operator present and verified off-VM Mac snapshots. Unattended cutover still
requires external monitoring and private recovery. Both Oracle units use
`state/cost-policy-runtime.json`; it remains COST_INCONCLUSIVE until actual review.

Oracle market-open preparation and actual broker check results are recorded in
[market-open preparation](../reviews/2026-10-24-c22-market-open-preparation.md).
The manual VM helper `/home/ubuntu/c22-demo/preparation/prepare_market_open.py`
refreshes read-only evidence, restores shadow and creates a conservative report;
it never activates sending. Run it before the chosen soak window because its
exclusive broker probe deliberately interrupts shadow. Pass an aware UTC
`--since` and, after supported attestation, an explicit `--cost-policy` path.
The staged execution service is a template only, without automatic boot enablement.
Neither a clean readiness report nor the opening of the market replaces owner
review/approval, supported cost evidence or the48h/96prospective-bar requirement.

1. Confirm trial30 journal `active=None`, no halt, empty pending outbox; live broker has no trial30-magic position/order; watcher stopped. Local status is not live broker proof.
2. Start at/after UTC midnight with no trial30 trade that UTC day. Candidate one-loss circuit counts candidate positions only.
3. Verify history/parity and shadow review accepted, explicit Demo identity, fresh cost policy, unchanged hashes.
4. Archive flat trial30 journal read-only; preserve original for rollback. Do not mutate or reuse it as candidate journal.
5. After owner execution approval:

```bash
make bot-execute
```

`make c22h4-run` is the same execution watcher. Calling the Python entrypoint with `--execute` and without `MT5_ENABLE_DEMO_ORDER_SEND=1` still fails before MT5 initialization. No notifier implicitly enabled; durable broker-confirmed outbox retained. First close: preserve closing deal magic/comment/position ID and full cash ledger to resolve E7; runner does not depend on exit magic.

Each blocked entry, broker-confirmed fill, and close appends `data/c22h4-demo-trades.md` plus a JSONL twin. A block reason is written once per UTC day. The note records entry price and the frozen signal rule, then on close the cash ledger, whether the exit matched the planned stop or target, and that a single trade does not authorize a contract change.

## Status, stop, rollback

```bash
make c22h4-status
make c22h4-stop
```

Status reads local journal and process list; stale heartbeat/process-unknown is not broker exposure proof. Before first candidate run no journal exists. Stop ends watcher only; existing broker SL/TP remain. Never delete UNKNOWN/SENDING state or safety halt to force new orders. Reconcile full broker evidence first.

Local correction2026-10-14: status reports execution mode separately from entry
readiness and cost expiry. `execution (เปิดส่ง)` means the execution flag is set;
it does not mean signal/admission/order_check passed. A valid local attestation
still leaves broker readiness unverified. `heartbeat` is a poll timestamp, not a
new setup. Last recorded blocker is historical and does not replace current
readiness. For a watcher using a custom cost file, pass the same path explicitly:
`python -m scripts.ops.c22h4_status --brief --cost-policy <path>`; otherwise status
checks the default shared policy. Status never renews attestation or mutates journal.

Current containment policy2026-10-23 supersedes the old process restart latch.
Baseline must have reconciled provenance and remain unchanged across restart.
Missing midnight floating equity blocks new entries for that UTC day; existing
positions remain managed. Never reset saved baseline/halt/UNKNOWN to force entry.
Confirmed partial10010 recovery still requires complete matching ledger,
consistent residual, no pending orders and stable position ID. Ticket changes
under that same ID are accepted; comments alone never establish ownership.

Rollback: candidate confirmed flat, empty reconciliation/outbox -> stop candidate
-> verify account flat and UTC-day circuit -> execution-time owner approval ->
`make trial30-execute`. `trial30-run/start` are shadow regardless of environment.
Only one host/sender may own this account; no automatic cross-machine failover.

## Durable evidence, costs and notifications

`audit_events` in the existing journal is append-only (SQLite update/delete
triggers). Financial state/event changes share one transaction; request audit is
committed before order_send. Response and reconciliation follow in separate
records. Crash after send may leave SENDING/UNKNOWN; resolve broker evidence,
never erase intent. Financial persistence failure blocks further mutation.
Existing `events` remains broker/critical notification outbox. Note consumers
replay durable lifecycle events across restart, independent of Telegram delivery;
Markdown/JSONL deduplicate stable event IDs. Lost HTTP acknowledgement can
produce duplicate Telegram messages with the same event ID, never another order.

v1/trial30 age24h; C22 v2 age168h. No automatic re-attestation. V2 carries
`evidence.tariff/spec/swap_calendar`, each `{document, sha256}`; SHA256 is over
`json.dumps(document, sort_keys=True, allow_nan=False).encode()`. All documents
require `source`. Tariff specifies `commission_per_lot` and
`unit=USD_per_lot_round_trip`. Spec `fields` includes contract/tick/volume min/max/
step, swap_mode/long/short/rollover3days and must equal current broker values.
Swap calendar `unit=USD_per_lot`, with `days[YYYY-MM-DD]` containing aware UTC
`rollover_utc`, signed `buy`/`sell` amounts including that day's holiday/triple-day
multiplier. Cover current day and each observed post-review closed position.
Missing coverage blocks; actual closed-deal swap/commission/fee drift blocks.
These are attested assumptions until verified against broker history. Cutover
requires <=24h evidence even if v2's runtime admission lifetime is168h.

Execution CLI requires explicit `MT5_TERMINAL_PATH`. Use a dedicated terminal,
Wine prefix and account. Account identity is checked before every mutation;
multiple SDK calls are not atomic. Never switch accounts manually in that terminal.

Explicit operator configuration only:
`DEMO_TELEGRAM_TOKEN` + `DEMO_TELEGRAM_CHAT_ID` enable lifecycle/critical/blocker
alerts; `DEMO_HEALTHCHECK_URL` enables bounded HTTP heartbeat with `/fail` on
critical protection uncertainty. Configure external dead-man alerts for a stopped
process or dead network. Local process-alive, admission readiness and protection
are separate fields. Unreconciled active position >=180s queues CRITICAL; regular
heartbeat cannot turn it into healthy protection. HTTP errors retry with bounded
backoff and wall deadline, capped response body and one daemon HTTP worker per
client. Stuck DNS/headers/body cannot stall financial management or spawn more
workers. At most one broker and blocker delivery plus one coalesced latest health
ping per cycle. No secrets enter audit or backup.

Weekly evidence, machine output under `runs/`:

```bash
python -m scripts.demo_runtime.evidence --journal data/c22h4-demo.sqlite3 --since 2026-10-16T00:00:00+00:00 --until 2026-10-23T00:00:00+00:00 --out runs/c22-weekly/evidence.json
python -m scripts.demo_runtime.backup --journal data/c22h4-demo.sqlite3 --directory runs/c22-backups
```

Evidence separates release/config cohorts, broker net USD/expectancy/PF/count,
sampled equity DD, shadow admissions and blocker-cycle counts. Poll counts are not
independent missed signals; missing broker/time coverage remains INCONCLUSIVE.
Write a human-reviewed weekly synthesis to `docs/reviews/YYYY-MM-DD-*.md`.
No legacy normalized-R qualification or trade-by-trade automatic strategy changes.
Any new baseline/latency economic comparison must run base+swap and stress+swap;
missing swap metadata means COST_INCONCLUSIVE and no run.

## Oracle compatibility, soak and cutover

The existing Oracle ARM VM now runs an isolated C22 **shadow** deployment.
`c22-demo-shadow.service` was enabled and started on2026-10-24 at04:41:37UTC;
first-cycle readiness and recovery checks are recorded in the
[compatibility/deployment record](../reviews/2026-10-24-oracle-wine-compatibility.md).
Sending remains disabled. No new paid cloud resource was created; the owner confirmed Free Tier selection in Oracle's web console. Billing entitlement was not independently queried; existing
private-bucket permissions remain unverified.

The owner supplied SSH access after earlier Termius probes. Strict host checking
is retained; private keys are never copied into releases or the VM. The working
stack uses privately wrapped Wine11.0 plus source-built QEMU at upstream commit
`586284af4c2cfa90fd61cff414b0deb77acd70f7`. Both MT5 and Python use QEMU; the
experimental binary prints11.1.50. Original Box64 startup still fails and is not
used by this service. The strict Windows read/write SEH controls pass after the
upstream trap-number correction. NumPy2.5.3/pandas3.0.5/MetaTrader5 5.0.6231 are
pinned in a separate Windows Python3.13.17 venv using hash-required wheels.

Dedicated terminal/account identity, connected state and flat exposure were
verified through the SDK, including a cold automatic terminal launch without
GUI interaction. AutoTrading remains off. C22 shadow may read with trading
permissions disabled; execution and every mutation retain strict permissions.
Oracle uses `--initialize-timeout-ms 90000`; default10000 remains unchanged for
other callers. Values outside1000..120000 fail before initialization.

The actual service definition is
[`c22-oracle-shadow.service`](../../deploy/c22-demo/c22-oracle-shadow.service).
It invokes the Windows C22 entrypoint directly under Xvfb, without `--execute`,
and forces the environment gate to0. The generic native host wrapper was observed
waiting on stdout inherited by MT5 after a once-run; it is not used here.
Runtime paths on the VM:

- `/home/ubuntu/c22-demo/current` -> verified release `d091bc6b810e792c`.
- `/home/ubuntu/c22-demo/state/c22h4-shadow.sqlite3`: durable shadow audit/state.
- `/home/ubuntu/c22-private/c22-shadow.env`: mode0600, dedicated credentials/paths.
- `/home/ubuntu/c22-qemu-demo._g86ow9b`: dedicated Wine prefix.
- `C:\tools\c22-runtime\Scripts\python.exe`: pinned Windows venv.
- `C:\tools\mt5-c22-demo\terminal64.exe`: dedicated terminal.

Do not launch another sender or another SDK probe while this service owns the
terminal. Stop only this unit before exclusive broker diagnostics:

```bash
sudo systemctl status c22-demo-shadow.service --no-pager
sudo journalctl -u c22-demo-shadow.service -n 40 --no-pager
sudo systemctl stop c22-demo-shadow.service
sudo systemctl start c22-demo-shadow.service
```

Observed connected service cycles confirm execute=false and flat broker exposure.
An owner-approved VM reboot on2026-10-24 at05:28UTC verified automatic startup
of C22, nginx and the existing Next.js application; local ports80/3000 returned200.
Kernel is now7.0.0-1013-oracle. All1866 pre-boot audit rows survived unchanged.
The first three-minute observation still contained18 connection-unknown samples
out of90. Short host uptime alone therefore does not guarantee connection
stability. Preserve those failures when reviewing subsequent observations;
process-alive and boot recovery do not qualify the48-hour soak. An unchanged
extension at05:34:54–05:37:54UTC passed90/90 fresh/flat samples; the initial
failures remain part of the qualification record. Telegram was
explicitly deferred by the owner; no Telegram/Healthchecks delivery is configured.

A fresh source/config SHA256 check runs before every start. Restart is bounded
at3 starts/300s with10s delay; stop covers the entire control group. This is a
shadow deployment, not sending cutover. Keep the existing local journal/history
and rollback files; the VM shadow journal does not replace their financial audit.

Initial broker history fetched100000M1 in49.4s, yielding6588completeM15 and
362completeH4: history gate passed. Terminal returned no200000-bar response;
that is not proof of unlimited/deeper history. Feed parity failed:40signal bars,
3direction/admission divergences,8geometry and40indicator divergences. Review
and explain these before any sending approval; never retune or accept them by
changing assertions. This parity probe compares feed/decision geometry only,
not new economic performance. Cost policy remains explicitly
`COST_INCONCLUSIVE`; do not re-attest by changing its timestamp.

The exact initialization correction is retained as
[`box64-wine-prereserve.patch`](../../deploy/c22-demo/box64-wine-prereserve.patch),
SHA256 `61e5ad7286a67016ea6ce08bcbfc67209b86dbaf3931f38057288c77efbc4a25`,
against Box64 commit `2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a`.
It corrects default reservation granularity and `start-end` parsing, without
removing Wine assertions. It is an initialization fix, not an MT5 compatibility
qualification. A fresh apply reproduced the exact VM source; parser cases went
from 11 mismatches out of13 to zero. Preserve the original binary for rollback.
Do not apply this patch to another Box64 version without checking its source and
rerunning the parser, fresh-prefix and child-process controls.

Timebox Box64/Wine/MT5/Windows Python on the actual VM to one engineering day.
Owner clarified on 2026-10-24 that no Windows machine or Windows VPS is
available. If compatibility fails within the timebox, stop this attempt and
record a host-compatibility blocker. Do not assume a Windows fallback, provision
a paid VPS or expand cloud spend without a separate owner decision.

After compatibility passes and original sender is stopped/account flat, run
shadow >=48h and >=96 complete M15 bars across UTC midnight. Exercise disconnect,
restart and boot recovery. Retain timestamps, exact cache, commands and broker
identity/history/parity; no evidence manufactured from local synthetic tests.
Templates bound restart to3 starts/300s, restart delay10s; systemd starts shadow.
The installed `c22-demo-backup.service`/timer uses Windows SQLite online backup,
integrity/checksum and local restore verification, retaining up to7 cumulative
snapshots without pruning source financial history. The real oneshot passed
while shadow ran, including a post-boot snapshot with2350 audit rows and a
separately verified restore/checksum. Daily schedule is02:10UTC with up to300s
jitter. Backup and
watcher share the dedicated Wine namespace; do not add PrivateTmp to either
without qualifying their Wine-server ownership again. Upload option requires an existing `NoPublicAccess` bucket;
credentials stay in private environment/OCI files. Configure and verify remote
7-snapshot retention and perform an actual bucket download/restore before approval;
local restore test alone does not prove cloud recovery. Bucket creation/ACL,
retention changes and service installation require deployment review.

Cutover retains history/parity, <=24h cost evidence, flat old sender, reconciled
journal/empty outbox and owner approval at execution time. 7 Demo days and shadow
gates establish operational evidence only; real-money profitability remains
INCONCLUSIVE/PROHIBITED pending a separate review.

## Offline runtime debugging

Shared implementation now lives in `scripts/demo_runtime`: runner orchestration,
admission, lifecycle, broker, journal, costs, CLI, Wine host and local status.
C22 owns detection/notes/cache; trial30 owns the rollback strategy adapter.
Existing ops entrypoints and compatibility imports remain supported.
Use [stage → module → tests → command map](../architecture/codebase-layout.md#debug-entrypoints)
and `make test-demo` before tracing runtime changes. Tests use synthetic brokers.
This structural change preserves known failure-matrix gaps and does not authorize
broker access, watcher restart or deployment, or change readiness.
