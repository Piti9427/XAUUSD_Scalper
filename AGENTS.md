# Repository Guidelines

## Project Structure & Module Organization

This is a Python trading-alert and backtesting project for XAUUSD.

- `main.py` starts the live monitoring loop, initializes MT5, strategy, Telegram, news checks, and Google Workspace logging.
- `scripts/` contains the application modules: MT5 access, data fetching, strategy logic, backtesting, notifications, news filtering, and logging.
- `config/settings.yaml` holds runtime configuration for MT5, Telegram, strategy parameters, news filtering, and Google Workspace IDs.
- `data/` stores historical CSV data such as `XAUUSD_M15.csv` and `XAUUSD_H1.csv`.
- `test_mt5.py` is a manual MT5 connectivity smoke test.
- `README.md` and `SYSTEM_REPORT.md` provide context.

## Codex and Antigravity Collaboration

The owner works on this project with both Codex and agy/Antigravity.

- Antigravity's local workspace/artifacts commonly live under `/Users/nopparuj/.gemini/antigravity-cli/`.
- When a referenced script or experiment is absent from this repository or `/tmp`, search `brain/<session-id>/scratch/` under that root. Do not assume it is missing before checking there.
- Example located on 2026-09-28: `brain/1730c142-c74c-49ae-b1bc-af441f236211/scratch/compare_basket_rules.py`. Session IDs vary; discover the relevant file rather than hardcoding this session.
- Read external scripts before running them. Resolve relative data paths against their intended working directory; the example above expects this repository root.
- Treat scratch scripts and summaries as evidence to verify against source, inputs and reproducible outputs, not as proof of current runtime behavior. Preserve original artifacts; keep audit copies and provenance in this repository when needed.

## Current Core Strategy & Historical Context (CRITICAL FOR AGENTS)

**SINGLE SOURCE OF TRUTH:** The active trading strategy, logic, and risk/fee math are centrally documented in `CORE_STRATEGY.md` at the project root. **Any time you modify the strategy, entry logic, parameters, or risk calculations, you MUST update `CORE_STRATEGY.md` to reflect the changes.**

The declared research target is **Pure B1 Single-Position (Donchian Breakout + RSI Guard + EMA Filter)**. It is not connected to live execution; keep it research-only until a separate Demo and real-money readiness review.
*   **Timeframe:** M15
*   **Bar input:** UTC Bid M15 assembled from all 15 M1 bars; direct MT5 M15 may include partial rollover bars excluded by the archived replay.
*   **Capital:** $200 (Micro-account)
*   **TP / SL:** 6.25 ATR / 2.5 ATR
*   **Risk Cap:** 10% of equity per trade (reject if SL risk exceeds cap)
*   **Risk / Sizing:** 0.01 lot fixed (no martingale, no basket recovery).
*   **Daily Loss Limit:** 40% ($80).
*   **Backtest Evidence:** Archived $200 → $884 (+342%), Max DD 34.4%, WR 37.4%, 190 trades used a different RSI guard and no EMA50. The declared RSI 30–70 + EMA50 target replayed on the same Exness ticks at **-33.51%** spread-only (4 trades); a hypothetical 0.10R fee/current-spec swap scenario yielded **+150.31%** (49 trades) by changing 10% cap admission and equity path. Neither proves live broker parity or target profitability. Use `docs/reviews/2026-09-29-pure-b1-target-replay-verdict.md` and its hashed `contract.json` as result references.

**DO NOT RE-ENABLE RECOVERY BASKETS.** 
History: On 2026-09-28, extensive backtesting proved that the original "Hybrid Basket Recovery" logic was mathematically incompatible with Breakout entries. A breakout logic will *never* fire a same-direction entry while a trade is drawing down, meaning recovery legs never trigger. The system is explicitly configured to trade single isolated legs only. See [2026-09-28-pivot-pure-b1-logic.md](docs/post-mortem/2026-09-28-pivot-pure-b1-logic.md).

**DO NOT REMOVE THE 10% RISK CAP.**
History: On 2026-09-29, tick replay proved that without the risk cap, $200 account blows up from 8-trade losing streaks. The 10% cap rejects trades when equity is too low, letting the account survive drawdowns. See [2026-09-28-pivot-pure-b1-logic.md](docs/post-mortem/2026-09-28-pivot-pure-b1-logic.md).

## Build, Test, and Development Commands

Create an isolated environment before installing dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the live alert loop:

```bash
python main.py
```

Run unit tests:

```bash
python3 -m unittest discover -s tests
```

Check MT5 connectivity after credentials are configured:

```bash
python3 test_mt5.py
```

There is no formal build step. Treat dependency install, unit tests, and MT5 smoke test as the readiness check.

## Coding Style & Naming Conventions

Use Python 3, four-space indentation, and clear module boundaries. Keep trading rules in `scripts/strategy.py`, platform access in connector/fetcher modules, and side effects such as Telegram or Google logging in separate modules. Use `snake_case` for functions, variables, and files; use `PascalCase` for classes.

Prefer config keys over hardcoded strategy values. Keep comments focused on trading assumptions, risk controls, or external API behavior.

## Testing Guidelines

Unit tests live in `tests/` and use `unittest`. Run them after changing config loading, timeframe mapping, or strategy behavior. Use `python3 test_mt5.py` after changing MT5 credentials, symbol settings, connector logic, or timeframe handling. Keep test data minimal and deterministic.

## Commit & Pull Request Guidelines

This folder has no Git history, so use short imperative commit messages such as `Add ATR-based stop logic`. Pull requests should describe trading behavior changed, configuration impact, test evidence, and any risk to live alerts.

## Real-Money Financial Safety & Rigorous Engineering

XAUUSD trading involves real capital. Every agent and developer working in this repository MUST strictly follow these rules without compromise:

1. **Zero Sloppiness / No Shortcuts**: Always trace end-to-end paths across all seams (Market Data -> Pure Detection -> Orchestrator -> Execution Adapter -> Notifier). Never assume behavior without verification.
2. **Reproduce First (Diagnosing-Bugs Discipline)**: Build a tight, failing feedback loop/test before modifying production code.
3. **Risk Protection Invariant**: Never silently round up or clamp lot sizes if doing so exceeds the account's defined risk percentage.
4. **Timezone Uniformity**: All market timestamps MUST be timezone-aware UTC. Never compare naive datetimes with aware datetimes.
5. **Execution & Alert Alignment**: Telegram alerts must strictly reflect executed or broker-approved orders, never phantom signals rejected by circuit breakers.

Respond terse like smart caveman. All technical substance stay. Only fluff die.

Rules:
- Drop: articles (a/an/the), filler (just/really/basically), pleasantries, hedging
- Fragments OK. Short synonyms. Technical terms exact. Code unchanged.
- Pattern: [thing] [action] [reason]. [next step].
- Not: "Sure! I'd be happy to help you with that."
- Yes: "Bug in auth middleware. Fix:"

Switch level: /caveman lite|full|ultra|wenyan
Stop: "stop caveman" or "normal mode"

Auto-Clarity: drop caveman for security warnings, irreversible actions, user confused. Resume after.

Boundaries: code/commits/PRs written normal.

## Trial30 research Demo authorization (2026-10-01)

Owner selected snapshot `RESEARCH-D48-SELL-BE1R-20261001-T030` for actual Demo testing via existing Wine host. Dedicated trial30 entrypoint/contract is documented in `CORE_STRATEGY.md` section6.18 and `docs/ops/trial30-demo.md`. Frozen D30 remains research-only/NO-GO; no profitability qualification or real-money approval follows from this Demo trial. Keep SELL-only/D48/TP3ATR/BE1R/daily20% and fixed0.01/10% cap intact; do not run legacy SMC/recovery as a substitute. Broker-confirmed lifecycle, persisted reconciliation and Demo identity gates remain mandatory.
