# B2 runtime design — BUY intrabar break-even trigger (2026-11-11)

Status: **Phase 1 (observe-only) implemented locally, not deployed; Phase 2 (acting) staged.** Owner chose Option A on 2026-11-11. Owner request: "Design B2 runtime".
Evidence: [profit-leak review](../reviews/2026-11-11-c22-26b8-profit-leaks.md) (B1 root cause, B2 10/12,
6/6 at $313). Real money remains PROHIBITED.

## 1. Behaviour change (exactly one)

| | Today (26b8) | B2 |
| --- | --- | --- |
| SELL BE trigger | first quote after each completed M15 close | unchanged |
| BUY BE trigger | first quote after each completed M15 close | **every manager cycle** with a fresh quote, plus the existing bar-close check |
| Trigger formula | `order_calc_profit(open → executable) − commission − slippage·0.01·contract ≥ risk` | identical |
| BE level, geometry, order_check, SLTP request, confirmation (`be_pending` → `BE_MOVED`) | — | identical |
| Entry, SL/TP, sizing, cap, daily guards, cooldown | — | identical |

Swap is still excluded from the trigger, as in replay and current runtime.

## 2. Why per-cycle polling is enough

- The VM sender runs `--watch` with the default `--poll 1.0` ([cli.py:44](../../scripts/demo_runtime/cli.py)).
  BE activation is evaluated only when `bar != active["last_be_bar"]` ([lifecycle.py:188](../../scripts/demo_runtime/lifecycle.py)).
- Polling sensitivity at $313 (`runs/c22-26b8-profit-leaks-2026-11-11/sens_B2.json`, diagnostic):

| Granularity | 2024-26 base net / DD | 2024-26 stress | 2023-24 base |
| --- | --- | --- | --- |
| native | 1923.60 / 30.26 | 1324.12 | −262.83 |
| tick | 1975.60 / 26.43 | 1388.31 | −200.24 |
| 5 s | 1970.03 / 26.43 | 1358.69 | −195.86 |
| 30 s | 1935.87 / 27.78 | 1358.69 | −200.76 |
| 60 s | 1906.16 / 27.78 (< native) | 1364.31 | −200.70 |

- **Requirement:** the effective BUY trigger interval must stay ≤ 5 s. Each journal row stores
  `be_trigger_lag_ms` (quote time − previous evaluation time). A rolling p95 above 5 s raises an
  operational alert. It does not block the trade, because the bar-close check remains as a fallback.
- **Unverified:** the 1 s figure is the CLI default, not a measurement. The Wine/box64 sender has a
  latency history (5-min restart fix, watchdog `--stale-seconds 180`). Before implementation, measure the
  real cycle interval read-only from VM journal/heartbeat data. Treat the extra per-cycle `order_calc_profit`
  call (only while a BUY is open) as a no-regression gate: cycle p99 and lock/busy errors must be no worse
  than the 7-day baseline (same gate as the 2026-11-10 hardening map).

## 3. Code changes (minimal seam)

1. **Strategy hook** (`scripts/c22_selected/strategy.py`): add `intrabar_protect(direction) -> bool`,
   returning True only for direction 1 when the loaded contract has `buy_protect_trigger == "quote"`.
   The shared base and the other adapters (c22h4, trial30) default to False, so their behaviour is
   unchanged.
2. **Lifecycle** (`scripts/demo_runtime/lifecycle.py`, BE activation block at about line 188). Change the condition to:
   `(bar != last_be_bar and closed > entry) or (ctx.strategy.intrabar_protect(direction) and tick.time_msc > entry_ms)`.
   - On the intrabar path, use the cycle's already validated `tick`, not `_first_quote(closed)`, with a
     **stricter freshness rule**: quote age ≤ 5 s and `time_msc` newer than the last evaluated intrabar quote.
     Otherwise skip, and the bar-close check remains the fallback. The cycle's generic 60 s freshness is too
     loose, since 60 s granularity erases the gain.
   - Store `be_activation_quote` with `source="intrabar"` and audit `BE_TRIGGER_INTRABAR`.
   - Do not touch `last_be_bar` on the intrabar path.
   - Everything after `protection_active=True` stays the existing code: geometry, `order_check`, identity/exposure
     recheck, `be_pending`, confirmation and no blind resend.
3. **No new rate guard.** Once `protection_active` is persisted, the existing code already retries
   geometry/`order_check`/modify every cycle; only `be_pending` short-circuits. B2 changes only *when*
   `protection_active` becomes True for BUY. It does not change the modify retry cadence, so SELL and
   current protection keep their behaviour.
4. **Contract/config:** see §5.
5. **Pins/fingerprint:** `demo_runtime/lifecycle.py` is not in any config `source_hashes`
   (c22h4/trial30 have none for demo_runtime; selected pins only market_data/diagnostics). It is part
   of the selected release file set via the base manifest, so the release fingerprint and watchdog
   `--expected-fingerprint` change. The c22h4/trial30 behaviour stays identical through the hook default.

## 4. Failure modes and guards

| Risk | Guard |
| --- | --- |
| Spike/bad tick triggers BE | Existing quote validation; BID used for BUY (executable side), same as replay. A spike only moves SL to BE, it does not close the trade. |
| Stops/freeze level blocks the modify | Existing `be_geometry` check; retry next cycle (rate-limited) |
| Modify sent, response lost | Existing `be_pending` + broker SL confirmation, no blind resend (BE10008 path) |
| Higher modify count vs broker limits | Expected about 152 BUY triggers / 2 years in replay (≈1.5/week); rate guard |
| Cycle latency grows (SDK slow) | `be_trigger_lag_ms` metric + alert; bar-close fallback |
| Restart mid-position | `protection_active`, `be_pending` and `be_done` are already persisted in journal `active` |
| SELL accidentally affected | Hook keyed on direction; explicit SELL regression test |

## 5. Contract governance — owner decision needed

B2 changes the protection rule, so `26b8bcd69e043653` no longer fully describes the behaviour.

- **Option A (recommended): new RulesID.**
  - Add `"buy_protect_trigger": "quote"` to the contract, which yields a new contract id.
  - Add a new snapshot, a `CORE_STRATEGY.md` section and a research proof that points to the leak review.
  - Update the source pins and release fingerprint (watchdog `--expected-fingerprint`).
  - Update the hard-coded `26b8bcd69e043653` references in `generations.py` / `renewal.py` /
    `execution.py`, which bind cost generations and reviews.
  - New execution review/approval. This is heavier, but it keeps the AGENTS.md "single source of truth" rule.
  - **Operational cost:** `generations.py`/`renewal.py` hard-bind `26b8bcd69e043653`, so a new RulesID most
    likely invalidates the installed cost generation. New entries are then blocked until a new cost generation
    is reviewed and installed. AGENTS.md forbids automatic renewal, so this needs an owner-attended step.
- **Option B: runtime-only management flag.**
  - Keep the RulesID and bind the flag in the execution review.
  - Fewer file touches, but the RulesID then hides a behaviour difference from parity/research.
  - Not recommended.

## 6. Tests (before any deploy)

Add to `tests/demo/test_c22_selected_execution.py` and `test_c22_selected_lifecycle_recovery.py`:
1. BUY: an intrabar quote reaching ≥1R sends a BE modify in the same cycle; one below 1R does not.
2. SELL: an identical intrabar profit does **not** trigger; the bar-close behaviour is byte-identical.
3. Shadow mode yields `SHADOW_BE` intrabar with no `order_send`/modify.
4. Stale/invalid quote: no trigger.
5. `be_geometry` and stop-level block; the rate guard limits retries.
6. Ambiguous modify → `be_pending` persists across restart; no resend.
7. c22h4/trial30 adapters are unchanged (hook default False).
8. Full suite: `python3 -m unittest discover -s tests`.

Research parity: the replay B2 engine and a runtime simulation on the same tick slice must pick the
same trigger tick for a fixed set of recorded BUY trades.

## 7. Rollout

1. Implement + tests locally. Independent review.
2. **Observe-only phase in the execution sender.** The shadow service cannot test this: it never fills,
   admission raises `foreign_exposure` while the sender's position is open, and it is inactive per 6.54.
   - Ship the hook with `observe_only=True`. Each cycle computes the BUY intrabar trigger and journals
     `BE_TRIGGER_INTRABAR_OBSERVED` (quote time, lag, would-be SL).
   - SLTP is still acted on only at bar close, so trading behaviour stays native.
   - Gate: **≥10 observed BUY triggers** (≈1.5/week in replay, so about 7 weeks; the live bot has had 0 BUY
     trades so far) plus the latency gate from §2. Compare each observed trigger with the native outcome of
     that trade.
3. Owner approval, then switch the execution service via the existing release procedure (flat account,
   empty outbox, maintenance revoke → deploy → verify fingerprint).
4. Rollback: redeploy the previous release, which has the hook disabled. Open positions continue under
   persisted BE state.

## 8. Evidence limits

- B2 was derived from discovery attribution (in-sample there). 2023-24 and 2020-22 are consistency checks only.
- It fails the strict 12/12 rule (2 stress $200 cells, cap/slot path).
- The 2020-22 and 2023-24 "consistency" gains come with large trade-count jumps (2020-22 stress $313
  183 → 293, 2023-24 base $313 225 → 271). Those are cap/path effects in accounts near ruin, not the
  direct BUY mechanism. The clean evidence is the matched-trade BUY attribution (+$88 base, +$26 stress at $200).
- Replay does not model broker modify latency or rejections.
- Final confirmation must come from shadow/forward data.

## 9. Decisions recorded 2026-11-11 (after owner chose Option A)

- **What "new RulesID" means here.** The new id is a *runtime contract id* derived from the parent:
  sha256({"parent_rules_id": "26b8bcd69e043653", "management": {...}})[:16]. Changing the research
  `Rules` dataclass would rehash every research rule id, campaign cell and parity proof, so it is
  left alone. `runner.py` already reports `research_rules_id` separately.
- **Observe-only ships under 26b8.** It does not change trading behaviour. Shipping it under a new id
  would invalidate the installed cost generation and block new entries for the whole observation
  period of roughly 7 weeks. The new id is activated only for Phase 2 (acting).
- **The magic number and comment prefix stay the same in Phase 2.** Daily-loss and cooldown history
  routing then stays continuous across the switch.
- **The invalid-config reason reuses `source_drift`.** It has an existing diagnostics remedy entry, so
  the pinned diagnostics registry does not change.
- **The VM cycle-latency measurement moves to "before deploy".** It has not been done yet.

Phase 1 implementation:
- `scripts/c22_selected/strategy.py`: `MANAGEMENT_ALLOWED`, `intrabar_protect()` and
  `intrabar_quote_max_age_ms`.
- `scripts/demo_runtime/lifecycle.py`: `_observe_intrabar_be`.
- `config/c22-selected-demo.json`: `management` and the strategy.py source hash.
- `tests/demo/test_c22_selected_intrabar_be.py`: 8 tests.
