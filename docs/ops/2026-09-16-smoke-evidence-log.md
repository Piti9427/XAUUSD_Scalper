# Smoke / infra evidence log (Issue #1)

## 2026-09-16 — local Mac smoke (retry @ `1f20ced`)

Command:
```bash
.venv/bin/python scripts/smoke_broker_identity.py --out docs/ops/2026-09-16-mac-smoke-retry.json
```

Result: `INCONCLUSIVE_INFRA` / `mt5_import_missing` (artifact: `docs/ops/2026-09-16-mac-smoke-retry.json`).

Interpretation: MetaTrader5 Python package unavailable on this Mac. Not strategy FAIL. Oracle ARM64 soak and Demo 12w still unexecuted.

## Tracker (resolved same day)

- Push OK: `feature/smc-v2-hardening` → `869b18a`
- Closed via `gh`: #3, #4, #2
- #1 remains OPEN until live Exness smoke + Oracle soak + Demo 12w
