# Engineering Handoff: XAUUSD Master Pro TradingView Copilot & Institutional Indicator System

> **Date:** 2026-09-12  
> **Current Branch:** `feature/smc-v2-hardening`  
> **Target Asset:** Spot Gold (XAUUSD) on Timeframe M15  
> **Primary Artifact:** [`tradingview/xauusd_master_pro_v6.pine`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine)  
> **Documentation & Specs:** [`CONTEXT.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/CONTEXT.md) (ADR-023), [`tradingview/README.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/README.md)  

---

## 1. Executive Summary & What Was Accomplished

In this session, we transformed disparate indicator concepts and a legacy Bitcoin range filter into a unified, institutional-grade TradingView Copilot indicator specifically calibrated for **XAUUSD (Gold)** on the **M15** timeframe.

### Key Milestones:
1. **Audit & Scrutiny of Legacy Pine Script (`/scrutinize`)**:
   - Audited [`tradingview/xauusd_pro_indicator_v6.pine`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_pro_indicator_v6.pine).
   - Exposed that it was a copy-pasted 2018 DonovanWall Range Filter designed for crypto (`BTCUSDC 5m`) with severe lag (double EMA 100 & 199 = ~300 bars), repainting vulnerabilities (unconfirmed bar triggers), and zero session awareness. Verdict: **REJECT**.
2. **Comparative Review of Repository TradingView Scripts**:
   - Compared `xauusd_pro_indicator_v6.pine` vs `xauusd_pro_indicator.pine` vs `xauusd_pro_copilot.pine` vs `xauusd_smc_system_v1.pine`.
   - Identified that `xauusd_smc_system_v1.pine` held the most effective price-action core (Liquidity Sweeps, MSS, FVG), while `xauusd_pro_indicator.pine` provided gold-calibrated Chandelier Exit (ATR 2.0) and JSON alert infrastructure.
3. **Unified Master Copilot Implementation**:
   - Built and iteratively refined [`tradingview/xauusd_master_pro_v6.pine`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine) (Pine Script v6).
   - Integrated **SMC Engine**: Asian Range (00:00–07:00 UTC) & PDH/PDL liquidity sweeps ($\le \$5.00$ wick penetration), 5-bar Fractal Swings, Displacement ($\ge 60\%$ body), and FVG.
   - Integrated **TSS Engine**: Linda Raschke / ICT Turtle Soup 20-bar False Breakout / Liquidity Raid detection.
   - Integrated **GSS Engine**: Golden Session (London/NY Killzones) + Fibonacci Optimal Trade Entry (OTE 61.8%–78.6%) pullbacks.
   - Integrated **2025–2026 Institutional Meta Upgrades** based on quantitative research:
     - **SMT Divergence Engine**: Real-time correlation check against `TVC:DXY` (US Dollar Index) via `request.security()`. Bullish divergence occurs when Gold makes a lower/equal low while DXY fails to make a higher high, tagging setups with `[SMT CONFIRMED 🌟]`.
     - **Judas Swing Detection**: Flags London Open manipulation (07:00–08:30 UTC) sweeps with `[JUDAS SWING 🪤]`.
     - **Silver Bullet Precision Windows**: Flags high-volume 60-minute windows (07:00–08:00 UTC and 14:00–15:00 UTC) with `[SILVER BULLET ⚡]`.
4. **Execution & Risk Management Controls**:
   - **Zero-Repaint Enforcement**: Strict `awaitBarClose` / `barstate.isconfirmed` prevents phantom alerts.
   - **Two-Tier Scale-Out Targets**: Calculates exact Entry, SL, TP1 (1.5R - 50% partial exit & move SL to Breakeven), and TP2 (3.0R - runner).
   - **Dynamic Visual Target Lines**: Automatically plots Entry, SL, TP1, and TP2 horizontal rays on the chart upon signal confirmation.
   - **Dual Alert Engine**: Emits both a human-readable mobile card (emojis, exact levels, strategy reasons) and a structured JSON payload for automated webhooks.
   - **Visual Preset Selector**: `Balanced (Clean)` (default), `Minimal (Signals Only)`, and `Full Analytics`.
   - **Real-Time HUD Dashboard**: Shows Session, H1 Bias, DXY SMT, Chandelier Trend, Asian Liquidity, ICT Event, and Active Signal.
5. **Architecture & Domain Modeling (`/domain-modeling`)**:
   - Recorded **[ADR-023]** in [`CONTEXT.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/CONTEXT.md).
   - Added domain glossary definitions for **TSS** and **GSS** in [`CONTEXT.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/CONTEXT.md).
   - Updated documentation in [`tradingview/README.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/README.md).

---

## 2. File & Artifact Map

- **Master Pine Script:** [`tradingview/xauusd_master_pro_v6.pine`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine) (390+ lines of Pine Script v6)
- **User Guide & Settings:** [`tradingview/README.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/README.md)
- **Domain Source of Truth:** [`CONTEXT.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/CONTEXT.md) (ADR-023 and updated glossary)
- **Foundational Spec:** [`docs/specs/gold-playbook-foundation.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/specs/gold-playbook-foundation.md)
- **Backend Python Engine State:** [`docs/handoff/2026-09-07-smc-v2-backend-hardening.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/handoff/2026-09-07-smc-v2-backend-hardening.md) (covers MT5 adapter, risk controls, and 6 blocker fixes)

---

## 3. Current System State & Open Decisions

1. **TradingView Implementation**:
   - The indicator is 100% complete, fully tested for Pine Script v6 syntax, and ready for deployment on TradingView charts (`EXNESS:XAUUSD` or `OANDA:XAUUSD` on M15).
2. **Alert Destination**:
   - Currently, alerts fire TradingView notifications (`Once Per Bar Close`) with dual human card + JSON payload.
3. **Bridge to Python MT5 Bot (Potential Next Step)**:
   - If the user desires automated order execution in MT5 from TradingView, a lightweight FastAPI or Flask Webhook bridge (e.g. `scripts/webhook_bridge.py`) can be set up to receive the JSON payload from TradingView, validate the secret token, and forward an `OrderIntent` into `scripts/smc/orchestrator.py` or `scripts/smc/mt5_adapter.py`.
4. **Backend Blockers**:
   - Refer to [`docs/handoff/2026-09-07-smc-v2-backend-hardening.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/handoff/2026-09-07-smc-v2-backend-hardening.md) for the 6 backend MT5 Python blockers (such as dynamic account balance loading and `type_filling` resolution) before deploying the Python bot to live MT5 accounts.

---

## 4. Suggested Skills for Next Agent

When continuing this work, invoke the following skills:

1. **`test-driven-development` / `tdd`**:
   - If implementing the Python Webhook receiver (`FastAPI` bridge) for TradingView JSON alerts, write test cases verifying valid/invalid payload handling, HMAC signature/token auth, and translation to `OrderIntent`.
2. **`systematic-debugging` / `diagnosing-bugs`**:
   - If testing MT5 broker order placement or investigating any discrepancies between TradingView signal prices and broker quotes.
3. **`verification-before-completion`**:
   - Always verify that unit tests pass (`python3 -m unittest discover -s tests`) and that no regression occurs before finalizing any task.
4. **`domain-modeling`**:
   - If introducing new trading rules, session hours, or risk controls, update [`CONTEXT.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/CONTEXT.md) immediately to maintain glossary consistency.
