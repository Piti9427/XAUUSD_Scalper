# C22H4 research Demo replacement

Implementation available; broker parity/shadow/cutover **pending**. Real money PROHIBITED. Same Demo account replaces trial30; never simultaneous runners. `make bot-*` now selects C22H4; explicit `make trial30-*` targets retain rollback. Research returns do not qualify profitability or broker costs.

Owner reaffirmed C22H4 as the new Demo strategy on 2026-10-04 and requested default runner replacement. Keep frozen `1af968e9ac6a26ea` contract unchanged while resolving readiness findings in [PR scrutiny](../reviews/2026-10-04-c22h4-pr-scrutinize.md). On2026-10-05 owner selected shadow as the default for `make bot-run`/`make bot-start`: no `--execute` unless the invoking shell supplies `MT5_ENABLE_DEMO_ORDER_SEND=1`. On2026-10-06 `make bot-execute` and `make c22h4-run` set that gate themselves. Make does not read it from `.env`. Both print the selected mode. On2026-10-07 a C22 process that finds an overnight position latches current equity as that UTC day's loss baseline instead of waiting for the next midnight. The same process keeps that number. Starting the process again latches the equity at the new start. The 10% daily-loss and 10% per-trade caps remain. Candidate PID/log paths are `data/c22h4-demo-watch.pid` and `data/c22h4-demo-watch.log`; exact cache is `data/c22h4-shadow-bars.csv`. PR merge and broker cutover are separate actions.

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

Owner re-attests `data/trial30-demo-cost-policy.json` <=24h using existing tariff/account evidence workflow in [trial30-demo.md](trial30-demo.md). Do not merely change timestamp to bypass validation. Shadow performs broker `order_check`, never `order_send` or phantom fill notifications.

```bash
make c22h4-once
make c22h4-shadow > data/c22h4-shadow.log 2>&1
```

Foreground watcher, Ctrl-C stops. Cache bootstraps once from 100000 M1 copied in 50000-bar pages; a single 100000 request is rejected when MaxBars is 100000. Updates from 5000-M1 tail per completed M15; only new bar runs full research detector. `data/c22h4-shadow-bars.csv` atomically stores exact causal prefix for offline `prepare_candidate` replay; output contains non-null `macro_ema` and cache size, durable journal includes same diagnostics. Cache divergence blocks then rebuilds; **any divergence fails this shadow gate**. `--cache-output` supports explicit alternative local evidence path.

Collect >=96 completed M15 bars spanning >=1 UTC midnight, no unexpected BLOCKED status, non-null macro, no cache divergence. Replay signal/WAIT reason on exact exported bars with frozen contract; duplicate-bar WAIT and expired entry windows must be distinguished. Shadow is plumbing evidence; signal frequency (~one per five days) means no observed signal alone proves nothing. Initial offline parity remains independent gate.

## Cutover: owner approval at execution time

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

Owner retained process-scoped daily baseline on2026-10-14. A multi-midnight
`day_start_floating_unknown` block remains possible; inspect its provenance and
history under this policy rather than resetting allowance. Safety-close recovery
can retry only a broker-confirmed partial10010 after complete ledger/residual and
no-pending-order checks. Ambiguous or legacy pending closes remain UNKNOWN until
complete broker evidence resolves them. Complete safety closures use real closing
cash components and exit-deal price, and keep safety halt. These local code changes
require a separately reviewed rollout; an already-running Python watcher retains
its loaded code. No restart or cost re-attestation was performed by the fix task.

Rollback only when candidate is confirmed flat with no pending reconciliation/outbox: stop candidate -> verify account flat and UTC-day circuit suitability -> owner-reviewed restart `MT5_ENABLE_DEMO_ORDER_SEND=1 make trial30-run` or `trial30-start`. Use `make trial30-status` and `make trial30-stop` for the old watcher. Candidate does not auto-close a valid position during shutdown. Terminal/VPN/sleep failures require restart reconciliation; same account guard is local, not distributed across machines/cloned workspaces.

## Offline runtime debugging

Shared implementation now lives in `scripts/demo_runtime`: runner orchestration,
admission, lifecycle, broker, journal, costs, CLI, Wine host and local status.
C22 owns detection/notes/cache; trial30 owns the rollback strategy adapter.
Existing ops entrypoints and compatibility imports remain supported.
Use [stage → module → tests → command map](../architecture/codebase-layout.md#debug-entrypoints)
and `make test-demo` before tracing runtime changes. Tests use synthetic brokers.
This structural change preserves known failure-matrix gaps and does not authorize
broker access, watcher restart or deployment, or change readiness.
