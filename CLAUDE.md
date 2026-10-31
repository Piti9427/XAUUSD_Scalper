# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

XAUUSD (spot gold) alert/copilot system for Exness MT5. Two independent strategy stacks coexist (ADR-015 in `CONTEXT.md`) — no facade, no shared code path beyond config/connector:

| Stack | Entry point | Modules | Timeframes | Logic |
| :--- | :--- | :--- | :--- | :--- |
| **v0 "EMA Sniper"** (legacy) | `main.py` | `scripts/strategy.py`, `scripts/backtester.py`, `scripts/notifier.py`, `scripts/news_service.py`, `scripts/gws_logger.py`, `scripts/insight_formatter.py` | M15 exec, H1/H4 trend | EMA 20/50 cross + RSI exhaustion + MFI, ATR SL/TP |
| **SMC v1** (current focus) | `smc_main.py` (also Docker `deploy/entrypoint.sh`) | `scripts/smc/` | M5 exec, H1 bias | Liquidity sweep → MSS → FVG limit entry |

Do not delete or refactor v0 when working on v1 unless asked.

`CONTEXT.md` is the canonical domain glossary + settled ADRs (001–016) for SMC v1 (partly in Thai). Read it before changing any trading rule; numeric thresholds there (sweep ≤ $5.00, displacement body ≥ 60%, FVG ≥ $0.50, SL buffer $0.30, SL cap $6.00, TTL 3 bars, sweep→MSS ≤ 6 bars, MSS→FVG ≤ 2 bars, TP 2R, BE at 1R, 2 losses/day circuit breaker, 30 min cooldown, killzones London 07:00–10:00 / NY 12:30–15:30 UTC, flat before 21:00 UTC) are settled decisions, not tunables to change casually. `specs/xauusd_system_v1_spec.md` and `plans/` hold the longer spec/roadmap/tickets; `tradingview/*.pine` are Pine Script v6 counterparts.

## Commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # MetaTrader5 only installs on win32
pip install -r requirements-viz.txt      # optional: matplotlib/mplfinance for chart snapshots

python3 -m unittest discover -s tests                         # all tests
python3 -m unittest tests.test_smc_orchestrator               # one module
python3 -m unittest tests.test_smc_orchestrator.TestSMCOrchestrator.test_ttl_expiration_after_3_bars  # one test
python3 -m py_compile main.py smc_main.py test_mt5.py scripts/*.py scripts/smc/*.py tests/*.py      # syntax check

python3 smc_main.py      # SMC v1 live loop (falls back to dry-run if MT5 connect fails)
python3 main.py          # v0 live loop
python3 test_mt5.py      # MT5 connectivity smoke test (needs real creds, Windows/Wine)
```

`pyproject.toml` configures pytest (`tests/`) and ruff (line-length 100, py310), but neither is in requirements; `unittest` is the documented runner. No build step. Run commands from repo root — imports are `scripts.*` and config path is relative (`config/settings.yaml`).

## SMC v1 architecture

Two-layer design (ADR-012): pure detection is broker-free and fully testable on macOS/Linux; all state lives in the orchestrator.

- `types.py` — shared dataclasses/enums: `LiquidityLevels`, `SetupSignal` (frozen), `OrderIntent` (frozen), mutable `Position` / `AccountState`. `AccountState` is the single mutable state object passed through every bar.
- `liquidity.py` `compute_liquidity_levels(df_m5, date)` → Asian range (00:00–07:00 UTC) + PDH/PDL.
- `structure.py` — primitives: 5-bar fractals, displacement, FVG, sweep check.
- `detection.py` `detect_smc_setup(...)` — **pure, stateless** seam: H1 EMA200 bias, killzone gate, spread guard, sweep→MSS→FVG window, SL cap → `Optional[SetupSignal]`. Must never import MetaTrader5.
- `orchestrator.py` `StrategyOrchestrator.on_bar(bar, account, setup_signal, ...)` — **stateful**; mutates `account` in place and returns `List[OrderIntent]`. Handles daily-date reset, rollover flat, BE at 1R, TP/SL resolution, pending-order TTL/fill, circuit breaker/cooldown, lot sizing via `risk.calculate_lot_size`.
- `mt5_adapter.py` `SMCExecutionAdapter.execute_intent(intent)` — only place intents touch the broker; degrades to dry-run when MT5 is unavailable and writes a lifecycle audit trail to SQLite (`data/smc_trades.db`).
- `news.py` `NewsManager` — ForexFactory calendar fetch, ±30 min blackout, pre-news (15 min) BE-or-close rule.
- `notifier.py` (Telegram cards), `chart.py` (dark-theme PNG, needs viz deps).
- `backtester.py` `SMCBacktester.run(df_m5, df_h1)` — walks M5 bar-by-bar through the **same** `detect_smc_setup` + `StrategyOrchestrator`, so live and backtest share logic.

Live loop (`smc_main.py`) per closed M5 bar: refresh news (4 h) → blackout check → spread (points→$ conversion: raw > 1.0 treated as points × 0.01) → fetch 500 M5 / 250 H1 → pre-news safeguard → liquidity → detection (only if flat, no pending order, no blackout) → `on_bar` → execute intents → milestone alerts using `Position.*_alerted` flags.

Known gaps worth knowing before editing:
- `StrategyOrchestrator`, `detect_smc_setup`, `SMCBacktester` take thresholds as constructor/kwarg defaults; `smc_main.py` only wires `mt5.*`, `telegram.*`, and `strategy.max_spread` from config. Other `strategy:` / `news:` keys in `settings.yaml.example` are not yet plumbed through.
- `AccountState` balance in `smc_main.py` is hardcoded (10000), not read from MT5.

## Config & data

- `config/settings.yaml` is gitignored; copy from `config/settings.yaml.example`. `scripts/config_loader.py` loads it (PyYAML, or a minimal fallback parser for 2-level YAML), applies env overrides (`XAUUSD_MT5_LOGIN`, `XAUUSD_MT5_PASSWORD`, `XAUUSD_MT5_SERVER`, `XAUUSD_SYMBOL`, `XAUUSD_TELEGRAM_TOKEN`, `XAUUSD_TELEGRAM_CHAT_ID`, `XAUUSD_GWS_*`; see `.env.example`), sets defaults, validates (`ConfigError`).
- `data/*.csv`, `*.db`, `*.png` are gitignored. SMC v1 requires MT5-format M5 CSV `time,open,high,low,close,tick_volume` (ADR-016); yfinance GC=F data used by v0 (`scripts/fetch_yfinance_data.py`, `scripts/run_validation.py`) is not valid input for v1.
- MetaTrader5 is Windows-only; `scripts/mt5_connector.py` and `scripts/smc/mt5_adapter.py` guard the import (`mt5 = None`) so everything else runs on macOS/Linux. Cloud deployment is Docker + Wine + Xvfb (`deploy/`).

## Conventions

- Tests: `unittest`, synthetic deterministic DataFrames built in `setUp` (see `tests/test_smc_backtester.py`). Times are tz-aware UTC; modules coerce naive datetimes to UTC.
- Trading rules go in `scripts/smc/` (v1) or `scripts/strategy.py` (v0); side effects (Telegram, SQLite, Google Workspace, MT5) stay in their own modules.
- Communication style rule shared across agent configs (`AGENTS.md`, `.cursor/rules/caveman.mdc`, `.github/copilot-instructions.md`): terse "caveman" replies; code, commits, and PRs written normally.
