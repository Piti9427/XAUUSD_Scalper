# XAUUSD Scalper Project

Selected Exness Demo replacement: **C22 + H4 EMA200**, frozen `RESEARCH-C22-H4EMA200-20261004`. Default `make bot-*` commands select C22H4; `make bot-run`/`make bot-start` start shadow without sending orders. `make bot-execute` and `make c22h4-run` send Demo orders when a signal passes the gates. `make trial30-*` retains rollback. No real-money use. See [Demo runbook](docs/ops/c22h4-demo.md); strategy math remains in [CORE_STRATEGY section6.33](CORE_STRATEGY.md).

- **Goal:** Implement a hybrid backtesting and real-time alert system for Gold (XAUUSD).
- **Strategy target (research only):** **Pure B1 Single-Position** (Donchian Breakout + RSI 30–70 + EMA 50) with 6.25 ATR TP, 2.5 ATR SL, and 10% Risk Cap. See [current target replay verdict](docs/reviews/2026-09-29-pure-b1-target-replay-verdict.md).
- **Architecture:** Python + MetaTrader 5 API / Webhook Bridge + Telegram Bot.

## 🔄 Recent Updates (2026-09-29)
- **Strategy Pivot In Research:** Target Pure B1 detection is separate from legacy live alert and webhook paths. Live execution remains NO-GO.
- **Risk Gate Built:** Target fixed 0.01 lot is checked against a strict **10% equity cap**, including modeled costs. The gate is not connected to `main.py`.
- **Replay Evidence:** Archived +342% tick result uses a different RSI guard and no EMA50. Target RSI 30–70 + EMA50 replay on the same saved Exness ticks returned -33.51% spread-only (4 trades). A hypothetical 0.10R fee/current-spec swap scenario returned +150.31% (49 trades) because it changed 10% risk admission; neither establishes target profitability or broker fill parity. See [target replay verdict](docs/reviews/2026-09-29-pure-b1-target-replay-verdict.md).
- **Tests:** Legacy SMC, frozen B1-FINAL, and target Pure B1 tests coexist; suite count alone does not prove live parity.

## Project Structure
- `scripts/c22h4`: Live Demo module. `make bot-execute` sends. `make bot-run` stays shadow.
- `scripts/trial30`: Shared cycle implementation and the rollback strategy.
- `scripts/research`: Hashed campaign sources. Leave the paths in place.
- `docs/`: Current index in `docs/README.md`. Older campaign notes are in `docs/archive/`.
- `main.py`: Legacy alert loop. It does not send C22 orders.

Do not use `main.py` as a Pure B1 live runner: it still evaluates wick rejection and can send signal alerts without broker order approval. The target signal remains in research pending further validation.

## Pure B1 read-only broker capture and Shadow

The Pure B1 Shadow entrypoint reads the configured Exness Demo MT5 terminal under Wine. It assembles M15 Bid bars only when all 15 Bid M1 minutes exist, matching the archived replay. It writes append-only JSONL and never submits orders or sends Telegram alerts. See [broker-bar parity audit](docs/reviews/2026-09-29-pure-b1-broker-bar-parity.md).

```bash
.venv/bin/python scripts/ops/run_b1_d_wine.py --script scripts/ops/mt5_wine_pure_b1_shadow.py
```

This runs one cycle using the ignored `.env` login. Day-start equity is sampled only during the first UTC second; missing boundary or later balance change rejects a signal. To supply costs, copy `config/pure_b1_shadow_cost_policy.example.json` to a private file, fill the target account fingerprint, current UTC review time, account-specific evidence SHA-256, round-trip commission in USD per lot, swap-free assertion and explicit adverse slippage allowance, then set `PURE_B1_COST_POLICY` to that file. This is an operator-attested Shadow assumption, not broker-verified historical cost or fill evidence. Missing, stale or wrong-account policy rejects admission. This is Shadow only; it does not enable Demo or real-money orders.

`smc_main.py` is offline-only. It refuses to start when MT5 connects because its local position state and fixed-balance sizing are not broker-reconciled. Its disconnected simulation disables Telegram alerts. Use the webhook bridge in dry-run or demo testing; neither path is certified for real-money trading.

## Runtime Notes
- Keep real MT5, Telegram, and Google Workspace secrets out of `config/settings.yaml`.
- Prefer environment overrides such as `XAUUSD_MT5_LOGIN`, `XAUUSD_MT5_PASSWORD`, `XAUUSD_MT5_SERVER`, `XAUUSD_TELEGRAM_TOKEN`, and `XAUUSD_TELEGRAM_CHAT_ID`.
- Telegram, Google Workspace, and news protection are disabled by default until configured.

## Verification
- Unit tests: `python3 -m unittest discover -s tests`
- Syntax check: `python3 -m py_compile main.py test_mt5.py scripts/*.py tests/*.py`
- MT5 smoke test after credentials are configured: `python3 test_mt5.py`

## Output Style
Alerts and journals are formatted as compact insights:

```text
BUY XAUUSD - Review setup before entry
Setup: MTF align + MSS wick rejection + RSI 34.80
Levels: Entry 2400.00 | TP 2410.00 | SL 2395.00
Risk: 1:2.00 | risk 5.00 | reward 10.00 | spread 12.00
Context: RSI 34.80 | ATR 4.20
Action: Use predefined SL; do not chase if price moves beyond planned BUY entry.
```
