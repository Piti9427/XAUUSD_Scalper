# Claude Code instructions for this repository

Read [`AGENTS.md`](AGENTS.md) in full for repository guidelines, module layout, testing, and historical C22 notes.

The **live** C22 Selected26b8 Demo bot is documented in [`docs/C22-OPERATIONS-PROCESS.md`](docs/C22-OPERATIONS-PROCESS.md). That file is the single source of truth for the running contract, release, runbooks, and research decisions. Update it after every action, as required below.

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
