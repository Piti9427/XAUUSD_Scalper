# Smoke / infra evidence log (Issue #1)

## 2026-09-16 — local Mac smoke attempt (updated)

Command:
```bash
.venv/bin/python scripts/smoke_broker_identity.py
```

Result:
```json
{
  "ok": false,
  "reasons": ["mt5_import_missing"],
  "infra_verdict": "INCONCLUSIVE_INFRA",
  "infra_detail": "mt5_unavailable_on_host"
}
```

Interpretation: `MetaTrader5` Python package unavailable on this host. Scored as **INCONCLUSIVE_INFRA** (not strategy FAIL). Oracle ARM64 soak and Demo 12w remain unexecuted.

GitHub issue close: MCP `issue_write` and `gh` both return 403 / invalid keyring for issues write; MCP also hit rate limit (~31m). Git push to `feature/smc-v2-hardening` works.
