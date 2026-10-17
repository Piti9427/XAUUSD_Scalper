---
name: circuit22+H4EMA200 Demo replacement
overview: Replace authorized trial30 on the existing Exness Demo account with research candidate variant_1af968e9ac6a26ea (circuit22 + closed H4 EMA200), reusing trial30's verified broker lifecycle generalized to both directions. Retire the broken Reward156DemoRunner. Research-only; real money remains PROHIBITED.
status: draft v2 — revised after scrutiny 2026-10-04; awaiting owner approval
source_session: agy conversation fe703e0d-7254-4cef-ba9e-a27c25243d27 (stopped on quota while researching blockers)
---

# circuit22+H4EMA200 Demo replacement

## Owner decisions (2026-10-04)

- Accept worst continuous DD ~39% provided every modeled view is net-positive.
- Candidate: `variant_1af968e9ac6a26ea` (circuit22 + closed H4 EMA200). Continuous swap-inclusive base/stress net +$291.55/+$278.71, worst DD 39.28% (`docs/reviews/2026-10-04-four-strategy-continuous-backtest.md`).
- Account: **replace trial30 on the same Demo account** (no parallel run: both runners treat the other's position as `foreign_exposure` and share one equity/day baseline).
- Retire `Reward156DemoRunner`.

Not claimed: research qualification, profitability, broker cost parity, real-money readiness.

## Frozen candidate contract

Exact research path: `scripts/research/reward156_search.py:prepare_candidate` with circuit22 seed + `macro_span=200`. Recipe `dict(circuit22_seed, macro_span=200)` reproduces `config_id == "1af968e9ac6a26ea"` (verified locally).

| Item | Value |
|---|---|
| BUY signal | RSI14 (campaign_signals formula, zero-loss→RSI 100) cross ≥25, delta>0, close>EMA50, EMA50 > EMA50[-4] |
| SELL signal | close < prior 96-bar low, close<EMA50, EMA50<EMA50[-4]; SELL wins conflicts |
| Macro gate | closed H4 EMA200 (`closed_h4_ema`): BUY needs close>EMA, SELL close<EMA; NaN EMA blocks |
| BUY exit | SL 1.5 ATR, TP 2.0 × rounded-stop distance, protection off |
| SELL exit | SL 2.5 ATR, TP 3 ATR, BE at net ≥1R on closed-bar first quote |
| Circuits | daily loss 10% of UTC-day start, max 1 losing exit per UTC day, cooldown 0, no BUY pause, all sessions |
| Risk | fixed 0.01, static 10% cost-inclusive cap (reject, never clamp) |

Geometry (`breakout_entry.prepare_entry`): entry = quote ± slippage; stop to tick grid toward risk; BUY target `|entry−stop|×RR`; risk `(|entry−stop|+slip)×factor+fee` — same formula as trial30 live. Research admits on balance, live on equity: equal because admission only when flat. Loss counting (`breakout_replay.close`): net = gross − fee + swap < 0, keyed by UTC day of exit.

## Verified blockers this plan resolves (current code)

1. `scripts/reward156/runner.py:272,281` call nonexistent `Journal.claim_active/record_event` → `AttributeError` before `order_send`.
2. `runner.py:297-305` declares `CLOSED` on missing position (ticket OR comment only), no deal ledger, fill-risk, safety close, or BE.
3. Candidate logic absent from any executable path; `mt5_wine_trial30.py` pins trial30 config.
4. `CORE_STRATEGY.md:453-454` claims "Demo Runner Ready"; `tests/test_reward156_demo.py:137` passes only because cycle dies early.

## Evidence ledger (scrutiny + repro, 2026-10-04)

| # | Hypothesis | Run | Result | Plan impact |
|---|---|---|---|---|
| E1 | `prepare_candidate` macro EMA derives from passed bars only | synthetic aligned M15, n = 333/3199/3216/3232/16000 | non-null EMA 0/0/17/33/12801; needs >200 complete H4 | Must feed long cached frame, not 5000-M1 window |
| E2 | Contract hash pins behavior | read `config_id` (`reward156_search.py:42-44`) | hashes dict only, not code | Pin research source sha256 too |
| E3 | trial30 daily limit parameterizable | grep `runner.py` | `0.20` hardcoded at :119, :201; `0.10` at :153, :200, :360 | Add to seam table |
| E4 | Shadow proves signal parity | read `runner.py:184-191`; trade rate ~120/2y | `SHADOW_ADMIT` holds no position; ~1 signal/5 days | Parity offline; shadow = plumbing only |
| E5 | Cost policy usable | `validate_policy` now | `invalid_or_stale` (reviewed 2026-10-02T06:09Z, 24h window, `costs.py:29`) | Owner re-attest every ≤24h |
| E6 | `pure_b1_bars` rejects M15 gaps | read `strategy.py:23-48` | checks UTC/order/alignment/OHLC only; gaps pass | Same as research M15 assembly; no change |
| E7 | SL/TP close deals carry strategy magic | searched repo/journal | **no evidence** (trial30 never closed a trade; events 0) | Use position_id route; verify on first Demo close |

## Design

Share code, don't copy.

- **Detector/levels:** live calls research `prepare_candidate` + `prepare_entry` with frozen contract. Startup asserts (a) `config_id == 1af968e9ac6a26ea`, (b) sha256 of `reward156_search.py`, `reward156_tuning.py`, `campaign_signals.py`, `breakout_entry.py`, `breakout_models.py`, `scripts/strategy.py` equals values pinned in `config/c22h4-demo.json`. Mismatch → `BLOCKED source_drift`, no entries; open-trade management continues.
- **Bar cache (E1):** keep long completed-M15 frame in memory. Bootstrap once from deep M1 history; afterwards append only newly completed M15 bars from the per-cycle 5000-M1 window, rejecting any overlap mismatch (`bar_cache_divergence` → rebuild). Run `prepare_candidate` on full cache once per new completed M15 bar; per-second cycles reuse the cached last row. Fewer than 201 complete H4 → `macro_warmup_insufficient`.
- **Lifecycle:** generalize `Trial30DemoRunner` SELL-hardcoded seams and limits to strategy hooks; trial30 = one hook implementation. Its 27 existing tests pass unchanged.
- **Journal:** reuse `scripts/trial30/journal.py` unchanged.

### Seams to generalize (`scripts/trial30/runner.py`)

| Line(s) | Hardcoded | Generalized |
|---|---|---|
| 107 | rejects non-SELL | `direction in allowed_sides` |
| 119, 201 | daily loss `0.20` (E3) | `daily_loss_limit` param |
| 153, 200, 360 | risk cap `0.10` | `risk_cap` param (candidate keeps 0.10) |
| 122-124, 141-143 | Bid entry, SL/TP side, `ORDER_TYPE_SELL` | per-direction quote/type; levels via hook |
| 157 | SELL stop geometry | direction-aware |
| 197 | fresh Bid compare | fresh Ask for BUY |
| 303 | `position.type != 1` | expected type from `active.direction` |
| 341-347, 412-418 | SELL profit calc | per-direction type; BUY unrealized on Bid |
| 386-439, 468 | BE always on, SELL rounding/geometry | per-side protection hook (BUY off, SELL BE1R); `_level(..., -direction)` |
| 165, 515 | `T30_` / `T30_SAFETY` | prefix from strategy (`C22_`) |
| new | — | `max_daily_losses` admission check |

### Daily circuits (restart-safe)

- 10% daily loss: existing `BrokerView._baseline` with candidate limit.
- One loss/day (E7-safe): from full deal history each cycle, opening deals (`entry==0`) matching `MAGIC` + `C22_` comment → `position_id`s → full ledger per position (same route as `runner.py:270-288`); position counts as a loss when net volume 0 and ledger cash < 0, day = UTC day of last closing deal. Does not depend on closing-deal magic.

## Phases

### Phase 0 — Read-only broker probe + offline parity (FIRST; may change design)
Wine host, no orders, no trial30 interference (journal not opened).
1. Max contiguous Bid M1 depth from `copy_rates_range`/`copy_rates_from_pos`; count complete M15 and complete H4 (16×M15); fetch latency.
2. Parity: build M15 from broker M1 over the archive overlap (≤2026-10-02), run `prepare_candidate` on broker bars vs archived Exness bars; compare per-bar `direction`, `macro_ema`, `atr`, levels.
3. Report: `docs/reviews/2026-10-0X-c22h4-history-probe.md`.

Gate:
- ≥201 complete H4 available, bootstrap fetch < 60 s.
- Identical admit/block decision on every signal bar in overlap; any divergence explained (missing M1 minute, rollover bar) and listed.

Fallback if depth/latency fails (decide with owner before Phase 2):
- (a) seed cache from archived Exness M15 + broker tail with overlap-equality check, or
- (b) persist cache to disk and grow it forward (delays first entry until warm).

### Phase 1 — Retire legacy runner, fix truth claim
- Delete `scripts/reward156/runner.py`, `scripts/reward156/__init__.py`, `tests/test_reward156_demo.py` (no other importers).
- **Keep** `config/reward156-demo.json`: `reward156_tuning.py:38,261` reads/hashes it as frozen research source.
- `CORE_STRATEGY.md:453-454`: replace "Demo Runner Ready" with retired/never-executable note citing scrutiny review.
- Gate: `python3 -m unittest discover -s tests` green.

### Phase 2 — Pure candidate module + bar cache (TDD)
- `scripts/c22h4/strategy.py`: `CONTRACT`, `SOURCE_HASHES` check, `BarCache` (bootstrap/append/divergence), `decide(cache, bid, ask, spec, costs, equity)`.
- Red tests first: hash/source-drift block; E1 regression (200 H4 → blocked, 201 → available); append-only overlap check; signal/levels equal research on fixture; BUY TP 2R rounded; SELL TP 3 ATR.

### Phase 3 — Bidirectional lifecycle extraction
- Generalize seams table behind hook object; trial30 hook reproduces current constants.
- Gate: all 27 `tests/test_trial30_demo.py` tests pass with zero edits.

### Phase 4 — Candidate runner + CLI
- `scripts/c22h4/runner.py` (hooks: decide, levels, side protection, limits 10%/1 loss, `MAGIC`, `C22_`, snapshot `RESEARCH-C22-H4EMA200-20261004`).
- `scripts/ops/mt5_wine_c22h4.py`, `scripts/ops/run_c22h4_wine.py`; pinned `config/c22h4-demo.json` (contract_id + source hashes); journal `data/c22h4-demo.sqlite3`; same `MT5_ENABLE_DEMO_ORDER_SEND=1` gate; cost policy path reused, validity enforced by existing `validate_policy`.
- Makefile `c22h4-*` targets; trial30 targets kept for rollback.

### Phase 5 — Lifecycle tests (public `cycle()`, full broker method surface)
Both directions:
- BUY fill: Ask entry, SL 1.5 ATR, TP 2R; `FILLED` only after position + opening deal.
- SELL fill + BE1R after closed bar; BUY never moves to BE.
- Rejected / partial 10010 → safety close / timeout 10012 → UNKNOWN no retry / send exception.
- Restart `SENDING`/`UNKNOWN` + empty positions/deals → stays UNKNOWN, no admission (blocker 2 regression).
- Post-fill risk >10% → safety close owned ticket only.
- Close via ledger incl swap/commission.
- One-loss circuit: closing deal with magic 0 and `[sl]` comment still counted (E7); survives restart.
- Daily 10% blocks (not 20%); `macro_warmup_insufficient`; `source_drift`; foreign trial30-magic position blocks.
- Outbox retry without resubmission.

### Phase 6 — Shadow on Demo (plumbing only, E4)
- Precondition: trial30 watcher stopped (owner) or flat; owner re-attests cost policy (E5).
- `--watch` without `--execute` for ≥ 96 completed M15 bars across ≥1 UTC midnight.
- Gate:
  - every cycle status in expected set, no unexpected `BLOCKED`;
  - `macro_ema` non-null;
  - cache never diverges;
  - each `SHADOW_ADMIT`/`WAIT` reason matches offline `prepare_candidate` on the same cached bars.
- Signal parity is proven in Phase 0, not here.

### Phase 7 — Cutover (owner approval at execution time)
1. Confirm trial30 flat: journal `active=None`, no trial30-magic position/order, outbox empty, watcher stopped. (2026-10-04 read: `active=None`, no halt, last cycle 2026-10-03 `quote_stale`; process state unverified from sandbox.)
2. Start at/after a UTC midnight with no trial30 trade that day (candidate loss count ignores trial30 losses).
3. Cost policy fresh (<24h).
4. Archive `data/trial30-demo.sqlite3` read-only; start `c22h4 --watch --execute`.
5. First broker close: record closing-deal `magic`/`comment` → resolve E7 in ledger.
6. Rollback: stop c22h4 when flat → restart trial30.

### Phase 8 — Docs
- `CORE_STRATEGY.md`: c22h4 Demo contract, risk/fee math, evidence links.
- `AGENTS.md`: replace trial30 authorization with c22h4 (owner-worded); keep real-money PROHIBITED, no recovery baskets, 10% cap.
- `docs/ops/c22h4-demo.md`: run/stop/rollback/status, daily policy re-attest.

## Verification summary

| Gate | Evidence |
|---|---|
| Signal parity | Phase 0 broker-vs-archive per-bar comparison |
| Code identity | contract hash + source sha256 startup check |
| No regression | trial30 27 tests unchanged + full `unittest discover` |
| Lifecycle | Phase 5 tests via public `cycle()` |
| Plumbing | Phase 6 shadow report |

## Open risks

- Broker M1 depth/latency (Phase 0 decides fallback).
- Daily 24h cost-policy re-attest is an operational dependency; lapse blocks entries (fail closed, by design).
- E7 unresolved until first Demo close; design does not depend on it.
- Two MT5 Python clients on one Wine terminal untested → Phase 0/6 avoid concurrent runners.
- Demo fills/swap ≠ archived ticks; Demo P/L is not profitability evidence.
