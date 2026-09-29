# Pure B1 Live Execution Scrutinize Review & Verdict

**Date:** 2026-09-29
**Review Type:** Deep Scrutinize (Backtest vs. Live Runtime End-to-End Parity)
**Target Strategy:** Pure B1 Single-Position (M15, TP 6.25 ATR, SL 2.5 ATR, Fixed 0.01 Lot, 10% Risk Cap, Recovery Disabled)
**Verdict:** ⛔ **NO-GO FOR REAL-MONEY LIVE EXECUTION**

**2026-09-29 follow-up:** Owner chose RSI 30–70 + EMA50 as a research-only target. A fresh cost-inclusive replay on the same saved ticks did not preserve archived +342% metrics; see [Pure B1 target replay verdict](2026-09-29-pure-b1-target-replay-verdict.md). No live integration was made.

---

## Scrutinize recheck — 2026-09-29 (2.7-year research claim)

**Decision: NO-GO for live capital and NO-GO for claiming the +700.4% result as execution-ready.** The owner kept RSI 30–70 + EMA50 research-only after the six-month tick replay. This review did not connect to MT5 or place an order.

**Data provenance answer:** The +700.4% run uses pinned public `Market-Data-Lab` M1 Bid/Ask CSVs, whose upstream dataset identifies Dukascopy as provider, covering January 2024 through the partial August 2026 file. `scripts/research/data.py:11-43` pins URL/commit and checks cache hashes; `data.py:129-138` resamples **Bid only** into M15 for this simulator. These are historical market prices, **not Exness chart prices or broker fills**. The distinct six-month capture manifest records Exness Demo `Exness-MT5Trial7`, `XAUUSDm`, 45,671,201 saved Bid/Ask ticks, and a capture-time 0.01-lot/100-oz/1:1000 snapshot. Its hashes and account metadata support the saved tape's internal provenance, but `order_api_called=false` and `historical_costs_measured=false`; they do not prove historical broker order approval or fills. The +341.99% replay uses this Exness tape with a different signal. Upstream source: https://github.com/kevingtlin/Market-Data-Lab/blob/922f83a60cc574e7395fb27397077288055a1ef6/XAUUSD_DUKASCOPY_M1_BID_ASK_README.md

**Broker condition follow-up:** Read-only Standard Demo/Exness Terminal inspection found published zero trading commission, currently qualified swap-free entitlement, and a USD 0.24 live spread snapshot. Exact spread distribution over saved Exness ticks and remaining execution-cost gaps are recorded in [XAUUSDm broker conditions audit](2026-09-29-xauusdm-broker-conditions-audit.md). The hypothetical 0.10R fee/current-spec swap replay is a stress scenario, not measured charges on this account.

**Timing issue:** `compare_b1_variants.py:55-65` evaluates breakout from completed `row['close']` and immediately assigns entry to that same close. A decision made after the M15 bar closes cannot generally fill at its historical closing quote; the first subsequent executable Bid/Ask quote must be used. This alone prevents the headline result from being interpreted as a tradable replay, even before costs.

| Severity | Finding | Evidence |
| --- | --- | --- |
| P0 | No Pure B1 execution path | `main.py:34,82-120` runs `XAUUSDSniperStrategy` wick rejection and sends Telegram before any broker approval. `pure_b1_bars()` is called by offline replay only; the separate fixed-lot 10% gate and replay's 40% daily gate are not integrated into a live Pure B1 orchestrator. |
| P0 | The headline backtest is an OHLC scenario, not the declared execution contract | `docs/research/archive/compare_b1_variants.py:40-85` enters at Bid M15 signal-bar close, checks later Bid OHLC highs/lows, and deducts a flat $0.30. It does not model Ask entry, observed spread at each fill, broker approval, slippage, commission, margin, or the 40% daily halt. Its `risk > balance * .10` check omits fill costs. |
| P0 | Tick evidence for the chosen signal is unstable under stated cost scenarios | On the saved 2026-03-28 to 2026-09-28 Bid/Ask ticks, the cost-inclusive 10% gate produced 4 trades / -33.51% / 36.12% DD with spread only; hypothetical 0.10R fee/current-spec swap produced 49 trades / +150.31% / 40.32% DD. Admission changes the subsequent equity path. The archived +341.99% used a different signal (RSI BUY <=75 / SELL >=25, no EMA50). See `2026-09-29-pure-b1-target-replay-verdict.md`. |
| P1 | Long-history score depends on simulator setup and modeled costs | Reran archived scripts against 64 checksum-verified monthly public M1 CSVs: `compare_b1_variants.py` reproduced $200 to $1,600.87 (+700.4%), 48.3% closed-equity DD, 36.3% WR, 325 trades. `compare_all_strategies.py` yielded +690.9%, 49.8% DD, 325 trades; its EMA200 `dropna()` delays the start. `stress_test_costs.py` yielded -34.5%, 68.0% DD with $0.30 + 0.10R fee, yet +297.8%, 56.7% DD with $0.80 + 0.10R. Non-monotonic results reflect path-dependent risk admission, not measured broker performance. Public M1 median spread was $0.62 per 0.01 lot, above the $0.30 flat OHLC assumption. |
| P1 | Research scripts still duplicate the signal arithmetic | The OHLC scripts calculate Donchian/RSI/EMA/ATR themselves. Independent comparison on 91,221 M15 bars found 490 signals in `pure_b1_bars()` and the archived formula, with zero direction mismatches. This supports signal parity on this input, not shared runtime behavior or fill parity. |

**Simplest next path:** Keep Pure B1 research-only. Freeze one versioned signal, fill, cost, and equity/risk contract; rerun it on representative broker Bid/Ask data with actual costs and a daily-loss gate. Then connect a separate Demo-only orchestrator to the shared detector and prove signal → risk admission → broker result → notification plus stop/TP and restart behavior. Reassess real-money readiness after Demo evidence and owner approval. The in-sample tournament ranking does not provide an independent holdout.

**Verification this recheck:** Archived 2.7-year variants, tournament, and cost-stress scripts rerun; 64 monthly cache files verified by source URL and SHA-256; 32 focused Pure B1/risk tests passed; `.venv/bin/python -m unittest discover -s tests -q` passed (623 tests, 2 skipped); `git diff --check` passed. System `python3` test run failed at import because it lacks project dependencies (`fastapi` among them); `.venv` is the project environment. No MT5 smoke or Demo lifecycle run.

---

## Recheck — 2026-09-29 (`$debug-mantra`)

**Verdict remains NO-GO.** User confirmed Pure B1 policy: fixed 0.01 lot, hard cap 10% of current equity. Existing webhook 5% sizing budget remains separate. No broker order, live alert, or Demo lifecycle was run.

| Breadcrumb | Runnable check / source | Observation | Conclusion |
| --- | --- | --- | --- |
| Reproduce | `calculate_lot_size(balance=200, entry_price=2600, sl_price=2588, risk_pct=.05, max_risk_cap_pct=.10)` | 0.01 lot risks $12.30; rejected at $10 budget | Generic sizing follows configured 5% budget |
| Disprove absolute-cap failure | Same call with `risk_pct=.10` | 0.01 lot accepted at $12.30 | 10% cap math works for this case; contract routing is wrong |
| Disprove unsafe approval | `sl_price=2579`, `risk_pct=.10` | $21.30 rejected against $20 cap | Cap blocks this over-limit case |
| Trace runtime | `main.py`, `scripts/strategy.py`, `scripts/run_staging_bridge.py`, `scripts/webhook/setup_place_limit.py` | `main.py` is legacy signal alert without order approval; bridge sizes external limit setups at 5% | Neither path runs Pure B1 fixed-lot execution |
| Cross-check replay | `scripts/research/b1_hybrid_six_month.py` → `scripts/research/b1_final.py:reference_bars()` versus `run_b1_breakdown.py` | Tick replay B1 uses RSI buy ≤75 / sell ≥25, with no EMA50; OHLC script uses RSI (30,70) and EMA50 | Claimed +342% tick result is **not proof** for the declared EMA50 strategy |

**Change made:** Added isolated `check_fixed_lot_risk()` with broker volume, current-equity, spread/slippage/commission, fixed 0.01 lot, and 10% cap checks. It does not change webhook sizing or place orders. `CORE_STRATEGY.md` now identifies target contract and evidence limits. Full regression: `.venv/bin/python -m unittest discover -s tests -q` passed (617 tests, 2 skipped). Target-file Ruff check/format and `git diff --check` passed. `make check` reached lint and failed on 43 findings in pre-existing, untracked scratch files (`fix_risk_tests.py`, `run_b1_breakdown.py`, `run_b1_ohlc.py`); those files were not modified. A prior run with system `python3` failed because PyYAML was absent; the repository `.venv` supplies it.

**Correction to original P0 risk wording:** `calculate_lot_size()` enforcing `risk_pct=.05` is correct for its generic webhook caller; changing its min-lot fallback to exceed that budget would violate the risk invariant. Its use as the Pure B1 gate would be wrong. The claim that this rejects “virtually all trades” was not measured against current signal and broker data.

**Additional P0:** Neither cited backtest verifies the full target signal and tick execution together. Freeze exact RSI/EMA indicator arithmetic, UTC bar-close handling, bid/ask fill and cost assumptions; rerun one reproducible tick replay under that contract before connecting market execution. The existing `b1_hybrid_six_month.py` metadata also retains legacy hybrid labels, so inspect executed code and output rather than relying on metadata alone.

**Remaining checklist:** Pure B1 signal/runtime, market order adapter, daily 40% equity gate, one-position enforcement, broker-approved notification, and Demo lifecycle remain unimplemented or unverified for this contract. Do not turn `dry_run` off or label this strategy live-ready based on the focused risk tests.

---

## 1. Executive Summary

A source trace compared the distinct tick replay and OHLC research scripts with production runtime entrypoints (`main.py`, `smc_main.py`, `scripts/run_staging_bridge.py`, `scripts/smc/risk.py`). The two research scripts do not prove the same signal contract.

The archived +342% tick and +690% OHLC figures use different signal and fill assumptions. **Current code cannot reproduce either result through a proven Pure B1 live path.** The generic 5% webhook sizing rejects setups that a separate fixed-lot 10% Pure B1 policy allows; no active execution entrypoint currently computes the declared Pure B1 signal.

---

## 2. Detailed Findings & Evidence

### [P0 - BLOCKER] Pure B1 Fixed-Lot Gate Is Not Wired Into Runtime
* **File & Lines:** [`scripts/smc/risk.py:121-148`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/risk.py#L121-L148)
* **Mechanism:**
  * In the backtest, micro-accounts ($200) execute fixed 0.01 lot as long as the SL risk does not exceed the **10% Risk Cap** ($20.00).
  * In `risk.py`, `effective_risk_pct = min(risk_pct, max_risk_cap_pct)`. When `risk_pct = 0.05` (5%) and `max_risk_cap_pct = 0.10` (10%), `effective_risk_pct` resolves to **0.05 ($10.00 budget)**.
  * When 0.01 lot risk exceeds $10.00, line 137 checks `if min_lot_risk > max_allowed_risk:`, triggering an order rejection:
    ```python
    reason = f"Small-account protection: min lot {min_lot} risks ${min_lot_risk:.2f} ({(min_lot_risk / capital) * 100:.2f}%), exceeding configured risk of {effective_risk_pct * 100:.1f}% (${max_allowed_risk:.2f})"
    ```
* **Empirical Verification:**
  Running `calculate_lot_size(balance=200, entry=2600, sl=2588, risk_pct=0.05, max_risk_cap_pct=0.10)` returned:
  `is_valid: False | reason: Small-account protection: min lot 0.01 risks $12.30 (6.15%), exceeding configured risk of 5.0% ($10.00)`
* **Recheck:** This 5% rejection is correct for generic webhook sizing. Pure B1 needs its separate fixed-lot gate, now implemented but not wired to a B1 runtime. No measured rejection rate supports the original “almost all trades” impact claim.

---

### [P0 - BLOCKER] Absence of an Executable Pure B1 Live Entrypoint
* **Files & Lines:**
  * [`main.py:6,34,84-120`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/main.py#L6-L120)
  * [`scripts/strategy.py:41-88`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/strategy.py#L41-L88)
  * [`smc_main.py:63-71`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/smc_main.py#L63-L71)
* **Mechanism:**
  1. `main.py` executes `XAUUSDSniperStrategy` (`scripts/strategy.py`), which uses an obsolete wick-rejection MSS logic (wick > 2x body) and NY session gate. It **does not compute Donchian Channel (30)** or **RSI Guard (30–70)**. Furthermore, it contains no broker order execution calls (only Telegram and Google Workspace alerts).
  2. `smc_main.py` contains an explicit safeguard at line 69 that raises `RuntimeError("SMC legacy loop live execution is disabled...")` if an active MT5 connection is detected.
  3. `scripts/run_staging_bridge.py` does not calculate signals; it passively waits for external TradingView `SETUP_PENDING` webhooks.
* **Impact:** Running `python main.py` or `python smc_main.py` on a live broker will either crash or broadcast alerts for an unverified legacy strategy rather than executing Pure B1.

---

### [RESOLVED AS FALSE POSITIVE] Target Ratio Wording (2.5R vs 6.25 ATR)
* **File & Lines:** [`scripts/run_staging_bridge.py:95`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/run_staging_bridge.py#L95), [`scripts/webhook_bridge.py:36-37`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/webhook_bridge.py#L36-L37)
* **Mechanism:**
  * Core Strategy requires **SL = 2.5 ATR**, **TP = 6.25 ATR**; this equals **2.5R**. The bridge's `tp_r=2.5` is arithmetically compatible if its SL geometry matches.
  * `partial_tp_enabled` defaults to `false` in `run_staging_bridge.py`; reading `partial_tp_r=1.0` does not enable partial exits. The bridge remains a separate external limit-order strategy, so this does not prove Pure B1 execution parity.

---

### [P1 - MAJOR] Execution Geometry Divergence (Limit vs. Market Orders)
* **File & Lines:** [`scripts/webhook/setup_place_limit.py:35`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/webhook/setup_place_limit.py#L35) vs [`scripts/research/b1_hybrid_six_month.py:408`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/b1_hybrid_six_month.py#L408)
* **Mechanism:**
  * Backtest assumes immediate market execution on the next tick following bar close (`entry_fill: first actual tick after signal`).
  * The Webhook Bridge submits `OrderIntentType.PLACE_LIMIT` with a 4-bar time-to-live (`order_ttl_bars`).
* **Impact:** Strong Donchian breakouts frequently expand without pulling back to the breakout bar close. Pending limit orders will be left unfilled, causing missed trades during major directional trends.

---

### [P1 - MAJOR] Daily Circuit Breaker Disconnect
* **File & Lines:** [`config/settings.yaml:66`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/config/settings.yaml#L66) vs [`scripts/run_staging_bridge.py:75`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/run_staging_bridge.py#L75)
* **Mechanism:**
  * The Pure B1 contract sets a **40% daily drawdown halt** ($80 on a $200 account).
  * `run_staging_bridge.py` enforces `max_daily_losses = wh_cfg.get("max_daily_losses", 2)` (halting trading after 2 discrete losing trades).
* **Impact:** If an account suffers two normal losses (e.g. -$12 and -$12 = -$24, only 12% DD), the bridge halts for the remainder of the UTC day, cutting off subsequent profitable entries despite 28% daily loss allowance remaining.

---

## 3. Remediation Checklist Before GO Decision

To safely achieve live parity with verified backtests, the following changes must be completed:

1. [x] **Add Pure B1 fixed-lot risk gate:** `check_fixed_lot_risk()` admits 0.01 only under 10% current-equity cap. Integration into Pure B1 runtime remains open. Generic `calculate_lot_size()` retains its configured budget.
2. [ ] **Implement Pure B1 Runtime Entrypoint (`main.py` or dedicated `b1_live.py`):**
   * Feed M15 candles from MT5 into pure detection: Donchian 30 breakout, RSI 14 in (30, 70), and EMA 50 trend alignment.
   * On confirmed signal at bar close, send Market Order (`ORDER_TYPE_BUY` / `ORDER_TYPE_SELL`) at 0.01 lot directly to MT5 with TP = `entry +/- (6.25 * ATR)` and SL = `entry -/+ (2.5 * ATR)`.
3. [ ] **Align Daily Circuit Breaker:**
   * Track cumulative daily realized loss against 40% equity instead of counting discrete losing orders.
4. [ ] **Demo Validation Gate:**
   * Run the unified entrypoint against an Exness Demo account to observe at least one end-to-end lifecycle (Signal → Risk Gate → Broker Market Order Fill → TP/SL Native Broker Trigger → Telegram Notification).
