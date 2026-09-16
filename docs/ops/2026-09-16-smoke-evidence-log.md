# Smoke / infra evidence log (Issue #1)

## 2026-09-16 — operator host confirmed Mac

Operator confirmed current host is macOS. Native MetaTrader5 Python IPC remains unavailable (`mt5_import_missing` / Wine IPC historically `-10003`/`-6`). Gate C live Exness identity smoke + Oracle soak + Demo 12w stay blocked on this host; need Windows/Oracle MT5 Python runtime.

## 2026-09-16 — local Mac smoke (retry @ `1f20ced`)

Command:
```bash
.venv/bin/python scripts/smoke_broker_identity.py --out docs/ops/2026-09-16-mac-smoke-retry.json
```

Result: `INCONCLUSIVE_INFRA` / `mt5_import_missing` (artifact: `docs/ops/2026-09-16-mac-smoke-retry.json`).

Interpretation: MetaTrader5 Python package unavailable on this Mac. Not strategy FAIL. Oracle ARM64 soak and Demo 12w still unexecuted.

## Tracker (resolved same day)

- Push OK: `feature/smc-v2-hardening` → `00b2e11` (Bugbot High: TP1/BE gate + live invent-PnL reject)
- Closed via `gh`: #3, #4, #2
- #1 remains OPEN until live Exness smoke + Oracle soak + Demo 12w
- PR: https://github.com/Piti9427/XAUUSD_Scalper/pull/5
