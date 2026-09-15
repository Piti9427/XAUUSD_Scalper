# Exness Demo Auto-Order Remediation Plan

## Goal

Run one automatically generated Pine Master Pro setup through TradingView, a broker-reconciled webhook bridge, and Exness Demo MT5 without exceeding 0.5% account risk or producing a phantom lifecycle alert.

Scope is Demo only. Real-money status remains `INCONCLUSIVE`.

## Architecture and ownership

Use one execution path:

`canonical Pine strategy -> authenticated intent webhook -> webhook_bridge -> MT5 Python on Windows/VPS -> BrokerLifecycleWorker -> durable outbox -> Telegram`

- Pine owns confirmed strategy setup detection and structural invalidation. It emits intent, never claims broker execution.
- Bridge owns schema admission, account policy, news/risk gates, idempotency, and broker submission.
- MT5 owns accepted orders, fills, prices, position state, and realized PnL.
- `BrokerLifecycleWorker` owns startup reconciliation, pending-order expiry, TP1/BE/close transitions, and lifecycle notifications derived from MT5 state.
- SQLite owns durable setup state, broker-ticket mapping, transition deduplication, and notification outbox.

Do not revive `smc_main.py` live execution. Do not automate Exness Web Terminal clicks. Do not use Pine lifecycle alerts as proof of broker state.

## Canonical identifiers

- `setup_id`: immutable business ID derived from canonical symbol, confirmed M15 bar-open UTC, direction, engine, and sorted contributors. Unique for the lifetime of the journal.
- `event_id`: immutable delivery ID. Unique per emitted intent. A replay with the same body is idempotent; the same ID with a different body is rejected as a conflict.
- `broker_ref`: fixed-length hash of `setup_id`, restricted to broker-safe ASCII and verified against the observed Exness comment limit. It is a recovery hint, not the primary key.
- MT5 ticket: authoritative broker identifier for each submitted child order and resulting position/deal.

Persist `setup_id -> broker_ref -> MT5 ticket(s)` before publishing any accepted notification. Replace the existing `order_id` contract atomically in schema, SQLite migration, adapter APIs, tests, and captured Pine fixtures; do not support two ambiguous correlation keys.

## Deterministic RED loops

Run first and keep failing until corresponding implementation exists:

```bash
.venv/bin/python docs/reviews/reproduce_demo_auto_order_plan_review.py
python3 -m unittest \
  tests.test_demo_command_schema \
  tests.test_execution_policy \
  tests.test_runtime_news_calendar \
  tests.test_broker_lifecycle_worker
```

Document repro covers missing design contracts. New unit/integration modules cover executable behavior; test names are planned files and must be added RED before production code.

## Work sequence

### 1. Pin intent contracts

- Canonical source: `tradingview/xauusd_master_pro_strategy.pine`.
- Accepted schema-v2 intent commands: `SETUP_PENDING` and `SETUP_CANCEL_REQUESTED` only. Reject Pine-originated fill, TP1, BE, and close events.
- `SETUP_PENDING` required fields: `schema`, `event`, `event_id`, `setup_id`, `simulation`, `symbol`, `timeframe`, `engine`, sorted contributors, `direction`, timezone-aware confirmed bar-open UTC, entry, structural SL, TP1, TP2, and TTL bars.
- `SETUP_CANCEL_REQUESTED` required fields: identifiers, confirmed event time, and one reason from the pinned cancellation vocabulary.
- Use Pydantic models with `extra="forbid"`. Reject non-finite prices, invalid price ordering, naive/malformed time, non-M15, non-XAUUSD canonical symbol, invalid direction, `simulation != true`, duplicate/conflicting IDs, and TTL outside configured bound.
- Validate cancellation only against an existing setup. It may cancel correlated pending tickets; it must never close a filled position merely because Pine thinks its simulated order is pending.

Check: schema tests fail before implementation and cover unknown fields, timestamp offsets, NaN/infinity, price ordering, replay, ID conflict, and cancel/fill race.

### 2. Establish executable broker policy

- Install MT5 terminal and Python `MetaTrader5` on a dedicated Windows/VPS host.
- Login to named Exness Demo account through terminal or process-secret environment. Never store credentials in tracked config.
- Introduce immutable `ExecutionPolicy` loaded from required environment variables: expected account fingerprint, expected server, allowed Demo trade mode, account currency, configured broker symbol alias, contract size, volume min/step/max, maximum tick age, maximum spread, and allowed order filling/time modes.
- Extend `scripts/mt5_readiness.py` to accept same policy and return `READY` only when every constraint matches. Otherwise return `BLOCKED` with per-check reasons. Keep it read-only.
- Extend adapter broker snapshot with login fingerprint, server, trade mode, symbol trade mode, tick UTC, bid/ask, stops/freeze levels, filling modes, and current exposure.
- Run same policy check at bridge startup, before admission, and again immediately before each `order_send`. A failed check leaves no claimed setup that blocks future recovery.

Check: fake-MT5 tests flip one policy field at a time. Every mismatch returns `BLOCKED` and asserts zero `order_send`.

### 3. Emit canonical Pine intents

- Add one `alert()` for `SETUP_PENDING` only after a confirmed M15 strategy setup and Pine-owned session/rollover gates pass.
- Pine may keep simulated capital sizing for backtest admission, but payload quantity is advisory and bridge ignores it. Broker equity, commission, slippage, and lot viability are bridge-only decisions.
- Generate deterministic IDs from canonical fields, independent of `bar_index`, reload count, or local timezone.
- Emit `SETUP_CANCEL_REQUESTED` when Pine-owned structural invalidation occurs while simulated setup remains pending. TTL/session/news/account cancellation remains bridge/worker-owned.
- Broker fill, accepted, TP1, BE, TP2, stop, and close alerts never originate from Pine.

Check: TradingView compile plus captured JSON fixtures prove exact schema, deterministic IDs after recalculation/reload, one setup emission per confirmed bar, and cancel intent ordering.

### 4. Harden webhook admission and durable claims

- Require a non-default secret from environment; application startup fails if absent or equal to known placeholder. Compare secrets in constant time.
- Expose TradingView ingress through authenticated HTTPS reverse proxy/tunnel. Bind Uvicorn to loopback or private interface only; do not expose default `0.0.0.0:8000` directly.
- Validate command before reading fields or mutating SQLite.
- In one SQLite transaction, insert immutable setup payload plus `RECEIVED` state, or return idempotent replay/conflict.
- Permit one active setup. Reconcile `SUBMITTING`, `PARTIALLY_SUBMITTED`, or `UNCERTAIN` state before admitting another.
- Never mark rejected guard outcomes as successfully processed unless replay semantics return same stored decision.

Check: replay tests cover bad auth, missing startup secret, malformed input, wrong account/server, duplicate, conflict, concurrent duplicate, timeout, restart, active exposure, and database-write failure.

### 5. Wire fail-closed risk and runtime news

- Produce a versioned runtime JSON calendar artifact containing normalized events, generation UTC, `coverage_start_utc`, `coverage_end_utc`, source identifier, and source hash. Pine generation may consume same normalized source but is not runtime artifact.
- Add loader that verifies schema, timezone, hash, freshness, and that broker-now lies inside declared coverage. Build `NewsManager` from validated events and pass it into `create_app`.
- Reject new setup when calendar is missing, empty without explicit source assertion, stale, malformed, or outside coverage.
- Require measured commission-per-lot and slippage allowance. Reject missing, negative, or stale calibration.
- Size from `min(balance, equity)` at 0.5%. Floor total volume to a step that splits into two broker-valid child lots. Never clamp upward. Reject when minimum split volume exceeds budget.
- Validate direction-specific entry/SL/TP ordering and estimate worst-case loss including spread, slippage, commission, and both child orders.
- Enforce broker-derived two realized losses, 30-minute cooldown, 5% start-of-day equity drawdown halt, live spread, rollover, and one-correlated-XAUUSD-exposure maximum.

Check: `$100` fixtures return `NOT_VIABLE` whenever minimum split volume breaches 0.5%. Boundary tests cover floating steps, cost inclusion, equity below balance, spread spike, calendar coverage edge, and UTC day reset.

### 6. Submit broker-native split orders safely

- Submit two equal pending child orders: TP1 leg and TP2 runner. Both use same structural SL; each child volume satisfies broker min/step. Store distinct child tickets.
- Persist `SUBMITTING` before first call. After each broker response, persist request digest, retcode, ticket, and state before sending next child.
- If child one succeeds and child two fails or becomes uncertain, stop submission, reconcile broker state, then cancel confirmed orphan pending exposure. Never retry blindly.
- Treat only broker-approved retcodes plus discovered ticket as accepted. Persist `PENDING` before enqueueing accepted notification.
- Use broker tickets for normal operations. Use `broker_ref` comment only for crash recovery, with collision detection against stored canonical setup data.

Check: deterministic fake-broker tests cover both accepted, first rejected, second rejected, timeout before response, timeout after broker acceptance, partial fill between child submissions, comment truncation, and restart after every durable write boundary.

### 7. Reconcile lifecycle with one durable worker

- Start exactly one `BrokerLifecycleWorker` using application lifespan hook. Complete startup reconciliation before `/ready` allows setup admission.
- Poll orders, positions, and deal history on configured interval with bounded backoff. Persist broker cursor/time overlap so delayed deal visibility cannot be skipped.
- State machine: `RECEIVED -> SUBMITTING -> PENDING -> FILLED -> TP1_DONE -> BE_DONE -> CLOSED`; side states: `REJECTED`, `CANCELLED`, `PARTIALLY_SUBMITTED`, `UNCERTAIN`, `RECONCILE_REQUIRED`.
- Derive fill, partial/full close, actual prices, volume, and net PnL from broker records. Net PnL includes profit, commission, swap, and fee.
- When broker confirms TP1 child closed at TP1, move runner SL to configured BE using its ticket. Persist command intent before call and broker result afterward. If modification is rejected or uncertain, reconcile; apply documented safety-close policy only after confirming current exposure.
- Cancel correlated pending child tickets when bridge-owned TTL, session end, validated news blackout, rollover, risk halt, account identity change, or explicit valid `SETUP_CANCEL_REQUESTED` occurs.
- Transactionally append each broker transition and durable outbox row with a unique transition key. Telegram dispatcher marks delivery separately; restart retries undelivered messages without recreating broker actions or duplicate lifecycle alerts.
- Unknown or ambiguous broker state keeps admission blocked and surfaces `RECONCILE_REQUIRED`; absence from one MT5 query is not proof of rejection or closure.

Check: fake-broker integration runs pending -> fill -> TP1 close -> BE modification -> TP2 close and pending -> cancellation. Restart at every transition. Duplicate/delayed broker records and Telegram failure produce one broker action and one eventual notification per transition.

### 8. Staged validation and Demo canary

1. **Offline contract:** run full unit suite, plan repro, schema fixtures, state-machine integration, and zero-network dry-run.
2. **Pine compile:** compile canonical script, capture setup/cancel JSON, and verify deterministic IDs plus Bar Magnifier behavior.
3. **Read-only broker policy:** run readiness against named Exness Demo policy; archive sanitized snapshot. No order API is reachable in this stage.
4. **Dry-run bridge:** replay captured Pine intent with `dry_run=true`; instrument adapter and assert zero `order_send`.
5. **Demo canary:** enable execution only after startup reconciliation returns ready. Wait for a naturally valid M15 setup. Immediately before submission, archive risk calculation, news coverage, spread, account identity, and empty exposure evidence.
6. Submit one setup, comprising exactly two correlated Demo child pending orders. Stop further admission after setup reaches `PENDING`; reconcile through terminal state.

Canary abort: disable admission first. Cancel only confirmed pending tickets. Do not close a filled Demo position without applying documented lifecycle safety policy and recording broker state.

## Acceptance evidence

- Offline contract, policy, news, lifecycle-worker, restart, and outbox tests pass.
- TradingView compile, captured fixtures, and Bar Magnifier result pass.
- Readiness returns `READY` for pinned Demo policy immediately before canary.
- Sanitized broker request/response receipts exist for both child orders and every later action.
- One `setup_id` maps to one `broker_ref`, two intended child tickets, discovered positions/deals, durable transitions, and notification keys without collision or duplication.
- Worst-case computed loss is at or below 0.5% of lower balance/equity; volume was floored and never raised to broker minimum.
- Every accepted/fill/TP1/BE/close Telegram alert has a preceding persisted broker-approved transition. Rejected/uncertain execution creates no success alert.
- Startup/restart reconciliation finishes without duplicate order, modification, close, or alert.

Passing these gates changes status only to `SOFTWARE_VERIFIED` for Demo canary mechanics. Historical expectancy, forward-demo duration, capital suitability, and real-money authorization remain separate and `INCONCLUSIVE`.
