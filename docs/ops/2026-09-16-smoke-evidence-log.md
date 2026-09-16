# Smoke / infra evidence log (Issue #1)

## 2026-09-16 — local Mac smoke attempt

Command:
```bash
.venv/bin/python scripts/smoke_broker_identity.py
```

Result:
```json
{"ok": false, "reasons": ["mt5_import_missing"]}
```

Interpretation: `MetaTrader5` Python package unavailable on this host. Not a PASS/FAIL of Exness Demo identity — environment lacks MT5 binding. Oracle ARM64 soak and Demo 12w remain unexecuted.

GitHub issue close: MCP `issue_write` and `gh` both return 403 / invalid keyring for issues write scope.
