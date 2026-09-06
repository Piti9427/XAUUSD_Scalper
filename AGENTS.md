# Repository Guidelines

## Project Structure & Module Organization

This is a Python trading-alert and backtesting project for XAUUSD.

- `main.py` starts the live monitoring loop, initializes MT5, strategy, Telegram, news checks, and Google Workspace logging.
- `scripts/` contains the application modules: MT5 access, data fetching, strategy logic, backtesting, notifications, news filtering, and logging.
- `config/settings.yaml` holds runtime configuration for MT5, Telegram, strategy parameters, news filtering, and Google Workspace IDs.
- `data/` stores historical CSV data such as `XAUUSD_M15.csv` and `XAUUSD_H1.csv`.
- `test_mt5.py` is a manual MT5 connectivity smoke test.
- `README.md` and `SYSTEM_REPORT.md` provide context.

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

## Security & Configuration Tips

Do not commit real MT5 credentials, Telegram tokens, chat IDs, spreadsheet IDs, or document IDs. Prefer env overrides for secrets. Validate spread, news pause windows, and symbol settings in demo mode before live use.

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
