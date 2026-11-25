# Repository Guidelines


<!-- BEGIN C22 live operations (mandatory, added 2026-11-25 ICT) -->

## C22 live operations documentation (mandatory, added 2026-11-25)

This section is the operating contract for any agent working on the live C22 Selected26b8 Demo bot. It does not replace the rest of this file. For the current live contract, release, runbooks, research decisions, and incident log, treat [`docs/C22-OPERATIONS-PROCESS.md`](docs/C22-OPERATIONS-PROCESS.md) as the **single source of truth** and keep it consistent with the VM. Do not treat `CORE_STRATEGY.md` section 6.33 or the opening of `docs/README.md` (legacy C22+H4 / `make bot-*`) as the live runbook.

### Mandatory documentation rule

After **any** of the actions below, update `docs/C22-OPERATIONS-PROCESS.md` in the same turn: the relevant section(s) **and** a changelog row with an Asia/Bangkok (ICT) timestamp. Link research outputs (reports, small CSVs, scripts) under `docs/research/YYYY-MM-DD/`. Keep the box mirror in sync at `/workspace/c22-trade-journal/docs-living/C22-OPERATIONS-PROCESS.md`. If the Mac is offline, write the box mirror and leave `/workspace/c22-trade-journal/docs-living/PENDING_MAC_SYNC`.

Actions that trigger an update include, without limitation:

- deploy or attempted deploy
- rollback
- review renewal or a change to the review / cost-policy pointer
- config or live strategy change (only after owner approval, a new release, and a review)
- backtest or research, including a decision to **keep** the current rules
- incident, mis-report, or lesson
- routine, alert, or watchdog change
- VM change (units, files, keys, firewall) — only after owner approval, except the pre-approved AP#1 `xdotool` reselect
- journal or research data sync

Do not invent numbers. If a fact is not verified, write `ยังไม่ยืนยัน`. Never commit unless the owner asks. Never commit or print secrets. See the process doc section 10 for the update procedure.

### Owner hard rules

1. **Demo only.** Real money is prohibited.
2. **Never close or modify positions** without the owner's explicit go-ahead.
3. **Confirm every VM change with the owner first.** Read-only inspection is allowed. The AP#1 `xdotool` reselect is pre-approved.
4. **No bypass** of the validator, review, cost policy, or source pins. Never hand-edit an expiry or a review file.
5. Keep the **10% risk cap**, the **daily stop**, and the **30-minute cooldown** (`cooldown_bars: 2` on M15).
6. Do **not** use the legacy `make bot-*` targets (those launch old C22, not Selected26b8).
7. Backtests run on the Mac or the assistant box, **never on the Oracle VM**.
8. Deploy only while **flat**, and never during **04:50**, **05:00–06:05**, or **06:50–07:10 ICT** (staging kits use slightly wider windows 04:45–06:10 and 06:45–07:15 ICT; use the wider window in practice).
9. Live strategy changes need **owner approval**, a **new release**, and a **review**.
10. Keep the Oracle VM and account strictly within **Always Free** limits (4 OCPU / 24 GB / 100 GB). Ask permission before anything that could exceed them or incur a charge.
11. **No repo commits** unless the owner explicitly asks.
12. **Never invent numbers.**
13. Credentials — owner quotes, verbatim:

> ย้ายเลย แต่ให้ claude อ่านหาเจอแต่ไม่ต้อง commit credentials keys or pass ขึ้นไป

> แต่ถ้าไม่ใส่ไว้ก็ต้องให้เรากรอกเองให้ด้วย เพราะมันจะได้ทำงาน ใช้งานได้

Document secret *locations* and environment-variable *names* only. Never write passwords, webhook URLs or tokens, private-key material, or API keys into the repo, chat, or this file. The owner fills values locally so the system can run.

### Key paths and commands (no secret values)

- Mac repo: `/Users/nopparuj/my-agents/XAUUSD_Scalper`
- Living process doc: `docs/C22-OPERATIONS-PROCESS.md`
- Box mirror: `/workspace/c22-trade-journal/docs-living/C22-OPERATIONS-PROCESS.md`
- Trade journal (box): `/workspace/c22-trade-journal/` — count bot trades with `owner == "bot"` only
- Mac journal copy (gitignored): `logs/trade-journal/`
- VM SSH from the box (VM clock is UTC): `ssh -i ~/.ssh/oracle_vm_ed25519 -o BatchMode=yes -o IdentitiesOnly=yes ubuntu@158.178.243.98`
- Mac SSH key path (do not print the key): `/Users/nopparuj/ssh-keys/ssh-key-2026-06-16.key`
- VM tree: `/home/ubuntu/c22-demo/` — journal `state/c22-selected-execution.sqlite3`, review pointer `state/c22-selected-execution-review.json`, policy pointer `state/cost-policy-runtime.json`
- Live service: `c22-selected-execution.service` (current release, contract, and review expiry are recorded in the process doc; read that file, do not copy stale IDs from here)
- Secret locations only: VM `~/c22-private/c22-shadow.env` (`XAUUSD_MT5_PASSWORD`, and related `XAUUSD_MT5_*` / Wine path variables), `/etc/c22-trade-notify.env` (`WEBHOOK_URL`, `WEBHOOK_AUTH`), and Mac `docs/handoff/credentials.local.env` (copy from `docs/handoff/credentials.local.example.env`). Those files, `docs/handoff/C22-*.md`, and `CLAUDE.local.md` are git-excluded. Never `git add -f` them.
- Rollback, renewal, and health-check commands: `docs/C22-OPERATIONS-PROCESS.md` sections 3–5.

<!-- END C22 live operations -->

## Project Structure & Module Organization

The active Oracle Demo adapter is `scripts/c22_selected` (C22 Selected26b8). Its execution service is `c22-selected-execution.service`; operational commands and limits are in `docs/ops/c22-selected-demo.md`. Legacy `make bot-execute` / `make bot-run` still target old C22 and must not be used to launch this version. Shared admission, journal, and broker reconciliation live in `scripts/demo_runtime`; the selected runner subclasses `DemoRunner` directly. Do not start `main.py`, `smc_main.py`, the webhook bridge, or `mql5/B1FinalEA.mq5` on the same account.

- `scripts/c22_selected` — current selected26b8 Demo adapter; one account, one sender.
- `scripts/c22h4` — retained frozen old C22 adapter and rollback contract; never concurrent with selected execution.
- `scripts/demo_runtime` — shared orchestration, admission, lifecycle, broker, journal, costs, CLI/host/status.
- `scripts/trial30` — retained rollback strategy adapter and compatibility imports. One account, one sender.
- `scripts/research` — campaign code. Paths are hashed. Do not relocate those files.
- `scripts/smc`, `scripts/webhook`, `scripts/pure_b1`, `scripts/reward156`, `main.py` — older stacks. They stay importable for their tests. They are outside the live interface.
- `config/settings.yaml` holds runtime configuration for MT5, Telegram, strategy parameters, news filtering, and Google Workspace IDs.
- `data/` stores historical CSV data such as `XAUUSD_M15.csv` and `XAUUSD_H1.csv`.
- `runs/` stores machine-generated experiment runs, simulation checkpoints, and large backtest output dumps. 100% gitignored.
- `docs/reviews/` stores human-readable review reports, verdicts, and audit summaries (*.md). Never write raw multi-file run dumps here.
- `test_mt5.py` is a manual MT5 connectivity smoke test.
- `README.md` and `SYSTEM_REPORT.md` provide context.

## Machine Experiment Outputs & Documentation Boundaries

- **`docs/reviews/` is STRICTLY for human-authored markdown reports (`*.md`)**. Never write multi-file simulation dumps, JSON cells, execution logs, or CSV tables directly into `docs/reviews/`.
- **All machine-generated test outputs, simulation runs, parameter tuning dumps, and checkpoints MUST be written to `runs/<campaign-name>/`** (or `data/research_output/`).
- The `runs/` directory is 100% ignored in `.gitignore` and must never be tracked or committed to Git.
- When an experiment or campaign concludes, author a synthesized summary markdown document in `docs/reviews/YYYY-MM-DD-<title>.md` citing the run metrics.

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

Run the Demo bot. `bot-execute` sends. `bot-run` does not:

```bash
make bot-execute
make bot-run
```

`python main.py` is the old alert loop. It does not send the C22 Demo orders.

Run unit tests:

```bash
python3 -m unittest discover -s tests
```

Check MT5 connectivity after credentials are configured:

```bash
python3 test_mt5.py
```

There is no formal build step. Treat dependency install, unit tests, and MT5 smoke test as the readiness check.

## Code Lookup

Query Codegraph before `cat`, `rg`, `grep`, or reading whole files. Cursor: one `codegraph_explore` call first; its source is Read-equivalent. Then `codegraph_search`, `codegraph_callers`, `codegraph_callees`, `codegraph_impact`, or `codegraph_files` as needed. Shell-only agents use `codegraph query|callers|callees|impact|files`. Do not re-grep a hit already returned. Read or grep only for a line Codegraph omitted, a file named in its staleness banner, or non-code (docs, plans, CSV, logs, lockfiles). If `.codegraph/` is missing, run `codegraph init -i` once. If Codegraph itself is unavailable, fall back to Read or grep. Do not use graphify for symbol lookup. Full rule: `.cursor/rules/codegraph-first.mdc`.

## Coding Style & Naming Conventions

Use Python 3, four-space indentation, and clear module boundaries. C22 entry rules live in `scripts/c22h4`. `scripts/strategy.py` is the old sniper alert strategy. Use `snake_case` for functions, variables, and files; use `PascalCase` for classes.

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

## C22H4 research Demo replacement selection (2026-10-04)

Owner selected `variant_1af968e9ac6a26ea` / snapshot `RESEARCH-C22-H4EMA200-20261004` to replace trial30 on the same existing Exness Demo account. Dedicated contract: `CORE_STRATEGY.md` section6.33, `config/c22h4-demo.json`, `docs/ops/c22h4-demo.md`. Keep archived RSI14cross25 BUY/96-bar SELL/EMA50/closed H4 EMA200, BUY SL1.5ATR/TP2 rounded R/no protection, SELL SL2.5ATR/TP3ATR/BE1R, daily10%/one losing exit per UTC day/fixed0.01/cost-inclusive10% cap intact. No recovery baskets; real money PROHIBITED; no research or profitability qualification inferred.

Implementation and read-only preparation authorized by replacement plan. Actual cutover requires owner approval at execution time after broker history/parity, 96-bar shadow spanning UTC midnight, fresh <=24h cost attestation, flat trial30/empty outbox/stopped watcher and no trial30 trade on cutover UTC day. Never run both strategies on same account concurrently. Broker-confirmed lifecycle, persisted reconciliation and Demo identity gates mandatory. Trial30 snapshot `RESEARCH-D48-SELL-BE1R-20261001-T030` remains retained rollback path with its original SELL-only/D48/TP3ATR/BE1R/daily20% contract. Do not substitute retired Reward156 runner or legacy SMC/recovery.


## Mandatory swap-inclusive research policy (2026-10-05)

Owner: "ตัดส่วน test ที่ไม่รวม swap ออกไปเลยทุกครั้งต่อไปให้ test แบบรวม swap ทุกครั้ง".
All new economic strategy backtests, comparisons, rankings and filter campaigns
MUST include modeled swap in every scenario. Run base+swap and stress+swap;
no new no-swap cell or economic qualification. Missing/unsupported swap metadata
blocks the run; never substitute zero or omit swap silently. Name rate/calendar
assumptions and retain costs-inconclusive status when broker history is unverified.
Archived frozen no-swap artifacts may be read to reproduce historical evidence,
but must not be rerun as a new economic evaluation or used for current selection.
Unit regressions of price/accounting/API behavior are not economic comparisons.
Do not rewrite frozen strategy/source pins or Demo contracts to alter archives.
Current active C22 diagnostics CLI follows this policy with two mandatory views.


## Selected26b8 Monday Demo forward trial (2026-10-25)

Owner explicitly requests actual MT5 Demo execution when Monday market data and
strategy signals arrive. Current contract is CORE_STRATEGY section6.54 and the
selected runbook. This latest decision authorizes an armed Demo sender, including
waiving48h/96bars/UTC-midnight waiting. It does not authorize real-money activity,
forced orders, native-rule changes or fabricated strict readiness/economic parity.

Distinct SELECTED_DEMO_ARMED_TRIAL binds current account/source/config/policy and
owner permission. New entries wait until Monday2026-10-26 Asia/Bangkok and a fresh
complete M15 after permission/start. Keep fixed0.01, cost-inclusive10% equitycap,
daily10%/loss2, cooldown, SL/TP/BE, identity/exposure/risk/margin/source checks and
persisted UNKNOWN/no-resend unchanged. Active/UNKNOWN managers must continue
reconciliation/protection if new-entry permission is revoked.

Swap-Free entitlement is UNKNOWN. New labelled regular-swap Demo assumptions
use fresh actual SDK POINTS rates and dated published schedule, never missing
zero. Economic qualification remains COST_INCONCLUSIVE; no old attestation is
fabricated. Existing exact observed cost/swap drift blocks later entries when
actual charges differ, including lower swap. No automatic cost-policy renewal.
The live Selected26b8 release `ff17` instead journals `SWAP_DRIFT_WARN` and does
not block entries on `swap_long`/`swap_short` drift (CORE_STRATEGY 6.73).
