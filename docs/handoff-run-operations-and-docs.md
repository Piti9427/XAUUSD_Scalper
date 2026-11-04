# Handoff: Execution Commands, Operations & Documentation Index

**Created Date**: 2026-10-30  
**Target Workspace**: `/Users/nopparuj/my-agents/XAUUSD_Scalper`  
**Purpose**: Comprehensive reference of all run commands, operations workflows (Local Mac & Remote Oracle VM), and `.md` documentation catalog for incoming agents and operators.

---

## 1. Environment & Architecture Overview

- **Local Machine (macOS)**:
  - Code analysis, unit tests, release bundling, attended monitoring, and snapshot audits.
  - Native Windows MT5 IPC is unavailable natively on macOS without Wine.
- **Remote Host (Oracle Cloud ARM64 Linux VM)**:
  - **IP**: `158.178.243.98` | **User**: `ubuntu` | **Working Directory**: `/home/ubuntu/c22-demo/`
  - **Stack**: Box64 + Wine 11.20 / QEMU User-Mode + Windows Python 3.14 + MetaTrader 5.
  - **Active Production Adapter**: C22 Selected26b8 (`scripts/c22_selected`) managed via systemd.
- **Safety Critical Invariants**:
  - Micro-account ($200 Demo), 0.01 lot fixed, 10% risk cap per trade, daily loss limit.
  - **Real money strictly prohibited**.
  - **Only one active sender/watcher per account** at any time.

---

## 2. Comprehensive Documentation Map (`.md`)

### A. Root Core Strategy & Instructions
- [`AGENTS.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/AGENTS.md): Canonical repository guidelines, build/test rules, code lookup rules, and caveman response standards.
- [`CORE_STRATEGY.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/CORE_STRATEGY.md): Single Source of Truth for all active strategy logic, parameters, risk/fee math, and historical pivots.
- [`README.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/README.md) & [`SYSTEM_REPORT.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/SYSTEM_REPORT.md): System introduction and architectural status.

### B. Architecture & System Summaries
- [`docs/PROJECT_SUMMARY.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/PROJECT_SUMMARY.md): Master summary of strategies, Oracle VM setup, Attended Market-Open protocol, and operational cheat-sheet.
- [`docs/CORE_ARCHITECTURE.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/CORE_ARCHITECTURE.md): Architectural layers and module separation.
- [`docs/architecture/codebase-layout.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/architecture/codebase-layout.md): Directory structure and boundaries.

### C. Operational Runbooks & Protocols (`docs/ops/`)
- [`docs/ops/c22-selected-demo.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/ops/c22-selected-demo.md): **Canonical active operations manual** for Selected26b8 (`scripts/c22_selected`). Covers packaging, systemd units, limits, and gate conditions.
- [`docs/ops/c22-attended-market-open.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/ops/c22-attended-market-open.md): Operator protocol for attended market open, console monitoring, and snapshot retrieval.
- [`docs/ops/c22h4-demo.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/ops/c22h4-demo.md): Operations manual for frozen old C22 adapter (retained rollback contract).
- [`docs/ops/trial30-demo.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/ops/trial30-demo.md): Operations manual for trial30 rollback strategy.
- [`docs/ops/B1_FINAL_RUNBOOK.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/ops/B1_FINAL_RUNBOOK.md): Archive runbook for historical Pure B1 single-position.
- [`docs/ops/c22-selected-reboot-proposal-2026-10-29.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/ops/c22-selected-reboot-proposal-2026-10-29.md): Verified procedure for Oracle VM reboot without corrupting journals.

### D. Critical Post-Mortems & Review Reports (`docs/reviews/`)
- [`docs/reviews/2026-10-24-oracle-wine-compatibility.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-10-24-oracle-wine-compatibility.md): Full technical log of Oracle ARM64 VM Box64/Wine/QEMU MT5 initialization patch and direct SSH validation.
- [`docs/reviews/2026-10-28-c22-sender-cutover.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-10-28-c22-sender-cutover.md): Verification of sender-only cutover on Oracle VM.
- [`docs/reviews/2026-10-28-c22-one-time-cost-install.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-10-28-c22-one-time-cost-install.md): Swap and fee policy verification and installation.
- [`docs/reviews/2026-10-30-c22-attended-maintenance-local.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-10-30-c22-attended-maintenance-local.md): Local implementation and verification of attended maintenance controller (`scripts/ops/attended_maintenance/`).

---

## 3. Execution Commands & Run Workflows

### A. Local Machine (macOS) — Testing & Validation

```bash
# 1. Run all code quality checks (compile, pip check, ruff lint, ruff format-check, unit tests)
make check

# 2. Fast lint & format
make lint
make format

# 3. Unit test discovery
make test

# 4. Demo Runtime offline tests (fast mock suite)
make test-demo

# 5. Verify Selected26b8 source integrity (hashes & pins)
PYTHONPATH=. .venv/bin/python -m scripts.c22_selected --verify-sources

# 6. Run targeted Selected26b8 unit tests
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests/demo -p 'test_c22_selected*.py' -v

# 7. Smoke test local MT5 connectivity (requires credentials in .env/config)
python3 test_mt5.py
```

---

### B. Remote Oracle VM — Deployment, Monitoring & Maintenance

#### 1. Attended Console & Snapshot (Run from Mac)
Connects to Oracle VM via SSH to monitor live states, ring local alert bell on state change, and download SQLite journal backups:

```bash
# Monitor live state with terminal bell on warnings/critical events
caffeinate -i python3 deploy/c22-demo/attended_session.py --watch

# Take a verified off-VM SQLite backup snapshot to Mac
python3 deploy/c22-demo/attended_session.py --snapshot runs/c22-attended-session/mac-backups
```

#### 2. Release Packaging (Build bundle on Mac before deployment to VM)
```bash
python3 deploy/c22-demo/prepare_selected_release.py --out runs/<new-release-dir>
```

#### 3. Systemd Services Management (On Oracle VM)
```bash
# Check status of Selected26b8 execution service
sudo systemctl status c22-selected-execution.service

# Check status of MT5 terminal service
sudo systemctl status c22-selected-terminal.service

# Check backup timer
sudo systemctl status c22-oracle-backup.timer

# View live systemd logs
journalctl -u c22-selected-execution.service -f
journalctl -u c22-selected-terminal.service -f
```

#### 4. Attended Maintenance Subsystem (`scripts/ops/attended_maintenance/`)
Deep module for atomic operations (AP measurement, cost updates, verified reboots):
- Entrypoint: [`scripts/ops/attended_maintenance/controller.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/ops/attended_maintenance/controller.py)
- Sub-actions: [`scripts/ops/attended_maintenance/actions.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/ops/attended_maintenance/actions.py)
- In-memory/SQLite store: [`scripts/ops/attended_maintenance/store.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/ops/attended_maintenance/store.py)

---

### C. Retained Rollback / Legacy Makefile Commands
> [!WARNING]
> Per `AGENTS.md`, legacy `make bot-execute` and `make bot-run` target the **old C22 adapter**, NOT the active Selected26b8. Do not use these shortcuts for Selected26b8.

- **Old C22 (Frozen)**:
  - `make c22h4-status`: Check journal & watcher process.
  - `make c22h4-once`: Run one read-only cycle.
  - `make c22h4-shadow`: Watch in shadow mode (no order send).
  - `make c22h4-run` (or `make bot-execute`): Execution mode on old C22.
  - `make c22h4-stop` (or `make bot-stop`): Stop old watcher safely.
- **Trial30 (Rollback Strategy)**:
  - `make trial30-status`
  - `make trial30-run` (Shadow)
  - `make trial30-execute` (Execution)
  - `make trial30-stop`

---

## 4. Suggested Skills for Incoming Agents

1. **`diagnosing-bugs`**: Use when investigating broker parity gaps, MT5 IPC timeouts, or state mismatches. Follows the strict 4-step discipline (reproduce, trace fail path, falsify hypothesis, cross-reference).
2. **`verification-before-completion`**: Mandatory check before claiming any task or test suite is passing or ready for deployment.
3. **`caveman`**: Communication rule in this repository (`AGENTS.md`) mandates smart caveman mode for terse, zero-fluff responses.
4. **`code-review`**: Use when validating branch/diff against project guidelines and specifications.
5. **`accidental-data-loss-prevention`**: Essential when dealing with VM journals, production-like SQLite databases, or systemd services.
