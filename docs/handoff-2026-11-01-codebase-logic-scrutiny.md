# Handoff: Codebase Logic Scrutiny & EA Bottrade Review

**Date**: 2026-11-01  
**Scope**: End-to-end review of EA trading bot logic, execution engine, risk controls, and system architecture for XAUUSDm automated trading on MT5.  
**Verdict**: ⛔ **REWORK** (Critical blockers identified in mathematical risk design, runtime fragility, and indicator calculation).  
**Primary Review Target**: C22 Selected26b8 (`scripts/c22_selected`) and shared runtime (`scripts/demo_runtime`).

---

## 1. Executive Summary

This session performed a comprehensive, outside-in scrutiny ([`/scrutinize`](file:///Users/nopparuj/.gemini/config/skills/scrutinize/SKILL.md)) of the XAUUSD automated EA bottrade codebase.

The repository exhibits significant **over-engineering and defensive sprawl** (~560 files) built around a Python trading loop executing over Wine IPC to MetaTrader 5. While the intention was to enforce strict risk controls and zero recovery/martingale, several severe flaws were identified:
1. **Mathematical Volatility Deadlock**: The fixed 10% risk cap on a $200 micro-account mathematically rejects virtually 100% of signals under normal Gold volatility (minimum broker volume 0.01 lot with 2.5 ATR stop loss requires >$20 budget whenever ATR14 > $7.50).
2. **Operational Fragility**: The live execution daemon computes SHA256 hashes of 24 Python files every bar and requires a 24-hour expiring JSON operator lease, causing silent halts and crashes on minor changes.
3. **Indicator Calculation Divergence**: The RSI filter uses Simple Moving Average (SMA) rolling means of gains and losses, diverging from MT5's standard Wilder's Exponential Smoothing (RMA) used by `iRSI`.
4. **Intra-bar Blindness in Break-Even**: The 1R profit protection checks only the opening quote of the subsequent M15 bar, completely ignoring intra-bar profit peaks.

---

## 2. Detailed Findings & Technical Evidence

### Finding 1 [BLOCKER]: Mathematical Volatility Deadlock on $200 Account
* **Locations**: [`scripts/smc/risk.py:83-93`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/risk.py#L83-L93), [`scripts/demo_runtime/admission.py:79-107`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py#L79-L107)
* **Mechanics**:
  * For XAUUSD (contract size 100), 0.01 lot equals $1 per dollar price movement.
  * Stop loss is set at $2.5 \times \text{ATR}$.
  * In normal M15 Gold market conditions, ATR14 fluctuates between $8.00 and $20.00.
  * At ATR = $10.00, SL distance is $25.00 ($25 risk) + spread + slippage + commission $\approx \$26.00$.
  * Max risk budget = $10\% \text{ of } \$200 = \$20.00$.
  * Since Exness does not support volumes below 0.01 lot, `check_fixed_lot_risk` rejects the trade.
* **Evidence**: [`CORE_STRATEGY.md:59`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/CORE_STRATEGY.md#L59) records that backtesting the pure target on tick history yielded only **4 trades** over the entire dataset due to this filter, finishing at -33.51%.
* **Remediation**:
  * Increase account capital baseline (e.g. $500–$1,000 for 0.01 lot), OR
  * Migrate to an Exness Cent account where contract size is smaller, allowing true micro-sizing.

---

### Finding 2 [BLOCKER]: Runtime Self-Hashing of 24 Files & Expiring Operator Leases
* **Locations**: [`scripts/c22_selected/strategy.py:70-91`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/strategy.py#L70-L91), [`scripts/c22_selected/execution.py:77-84`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/execution.py#L77-L84), [`scripts/c22_selected/__main__.py:53-55`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/__main__.py#L53-L55)
* **Mechanics**:
  * `verify_sources(self.config)` runs inside every 15-minute bar cycle, computing SHA256 hashes of 24 Python source files. Any docstring, comment, or format edit crashes the live bot with `source_drift`.
  * The `--execute` flag requires `--execution-review <path>`, where the lease expires after 24 hours (or 168 hours in v2). If not manually re-signed, the bot halts order admission.
* **Remediation**:
  * Decouple research provenance tracking from the live production execution loop.
  * Use Git commit hashes or container image digests for version tracking rather than runtime file self-hashing.

---

### Finding 3 [MAJOR]: Non-Standard RSI Formula (SMA vs Wilder's Smoothing)
* **Location**: [`scripts/research/campaign_signals.py:72-76`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/campaign_signals.py#L72-L76)
* **Mechanics**:
  * Gain and loss are calculated using `.rolling(period).mean()` (Simple Moving Average).
  * Standard technical analysis and MetaTrader 5's native `iRSI()` use Wilder's Exponential Smoothing (`ewm(alpha=1/period, adjust=False)`).
  * Consequently, RSI signals in Python diverge from indicators observed on MT5 charts or native MQL5 EAs.
* **Remediation**:
  * Switch to exponential smoothing `ewm(alpha=1/period, adjust=False)` for standard Wilder's RSI parity, or explicitly document it as a proprietary non-Wilder oscillator.

---

### Finding 4 [MAJOR]: 90-Second Admission Window & 60-Second Quote Stale Timeout over Wine IPC
* **Locations**: [`scripts/demo_runtime/admission.py:55-60`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py#L55-L60), [`scripts/demo_runtime/broker.py:270-272`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/broker.py#L270-L272)
* **Mechanics**:
  * The cycle must run and transmit an order within 90 seconds of bar close (`now - closed > 90s` triggers `entry_window_expired`).
  * In each cycle, the runner fetches 5,000 M1 bars over Wine IPC, resamples them, checks 24 file hashes, and executes SQLite operations.
  * Network jitter or Wine lag easily causes the cycle to breach the 90-second entry window or the 60-second quote freshness window (`quote_stale`), causing valid trades to be dropped permanently.
* **Remediation**:
  * Implement incremental bar updates (fetch only recent closed M1 bars instead of 5,000 bars every cycle).
  * Pre-compute or cache indicator values.

---

### Finding 5 [MAJOR]: Break-Even Trigger Ignores Intra-Bar Profit Peaks
* **Location**: [`scripts/demo_runtime/lifecycle.py:188-212`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/lifecycle.py#L188-L212)
* **Mechanics**:
  * The break-even condition ($\text{Net Profit} \ge 1R$) is evaluated strictly at the single quote immediately following the M15 close (`first_quote`).
  * If price reaches $+1.8R$ mid-bar and pulls back to $+0.8R$ by the close, the BE trigger is not armed. If price subsequent reverses and hits the initial stop loss, a full $1R$ loss is incurred.
* **Remediation**:
  * Monitor candle high/low (or tick extremes) to arm the BE trigger when price touches $1R$ intra-bar, or utilize server-side MT5 stop management.

---

### Finding 6 [MAJOR]: Hyper-sensitive Safety Kill-Switch
* **Locations**: [`scripts/demo_runtime/lifecycle.py:132-136`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/lifecycle.py#L132-L136), [`scripts/demo_runtime/lifecycle.py:290-297`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/lifecycle.py#L290-L297)
* **Mechanics**:
  * If actual broker commission exceeds the declared policy by even $0.00000001 (`observed_cost > active["commission"] + 1e-8`), the bot executes `_safety_close()` and locks into `safety_halt`.
  * If the broker normalizes or slips Take Profit by more than 0.5 tick (0.005 on Gold), it triggers `filled_stop_target_violation` and market-closes the active position.
* **Remediation**:
  * Add sensible floating-point tolerances ($0.05–$0.10) for commission and level quantization.

---

## 3. Architecture & Operational Context

* **Operating Environment**:
  * Local: macOS (Analysis, testing, review generation).
  * Production Remote: Oracle Cloud ARM64 Linux VM (`158.178.243.98`), Box64 + Wine + MT5 Windows Terminal running `c22-selected-execution.service`.
* **Strategy Invariant**: Single position only. No recovery baskets, no martingale. Fixed 0.01 lot.
* **Reference Operations Manual**: [`docs/ops/c22-selected-demo.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/ops/c22-selected-demo.md)
* **Canonical Strategy Specification**: [`CORE_STRATEGY.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/CORE_STRATEGY.md)

---

## 4. Recommended Action Plan for Next Session

1. **Phase 1: Mathematical Viability (High Priority)**
   * Determine capital sizing: Either increase Demo capital to $500–$1,000 or adjust the ATR stop multiplier / evaluation criteria so that 0.01 lot does not breach the 10% risk cap during normal volatility.
2. **Phase 2: Fix Indicator Parity**
   * Review `scripts/research/campaign_signals.py` and align RSI calculation with Wilder's RMA formula (`ewm(alpha=1/period, adjust=False)`).
3. **Phase 3: Streamline Execution Daemon**
   * Remove runtime `verify_sources()` and 24h lease checks from the core execution loop in `scripts/c22_selected/runner.py` and `scripts/c22_selected/strategy.py`.
   * Implement incremental M1 bar fetching to reduce cycle latency below 5 seconds.
4. **Phase 4: Long-term Native EA Transition (Strategic)**
   * Consider implementing the core breakout logic (Donchian 48 / RSI / EMA50 / H4 EMA200) natively in MQL5 under `mql5/` to eliminate Wine IPC latency, quote staleness, and complex external state machines entirely.

---

## 5. Suggested Skills for Incoming Agent

When picking up this work, the incoming agent should invoke the following skills:
* **`diagnosing-bugs` / `debug-mantra`**: For isolating the exact failure points in MT5 order admission and IPC timing.
* **`test-driven-development` / `tdd`**: For writing regression unit tests before modifying `risk.py` or `campaign_signals.py`.
* **`codebase-design`**: For decoupling the bloated research modules from the production execution path.
* **`verification-before-completion`**: For verifying end-to-end test suites and synthetic broker fixtures before claiming fixes.
