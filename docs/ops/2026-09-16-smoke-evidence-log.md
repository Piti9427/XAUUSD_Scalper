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

## 2026-09-16 — Wine terminal running re-probe @ `353771f`

`terminal64.exe` was running under MetaTrader 5.app Wine. Wine-Python
`mt5.initialize(path=...)` still returned `[-6, "Terminal: Authorization failed"]`.

Bases present: `MetaQuotes-Demo` only (no Exness). `config/settings.yaml` has
empty login/password/server.

Artifact: `docs/ops/2026-09-16-mac-wine-reprobe-running.json`  
Verdict: still `INCONCLUSIVE_INFRA` — not Gate C PASS.

## 2026-09-16 — Wine re-probe while terminal still up @ `d7ebd5f`

`terminal64.exe` still running. Native `.venv` smoke → `mt5_import_missing`
(`docs/ops/2026-09-16-exness-smoke-mac-retry.json`). Wine-Python initialize
with path still `[-6, "Terminal: Authorization failed"]`; account fields null;
no Exness server string.

Artifact: `docs/ops/2026-09-16-mac-wine-reprobe-running.json` (refreshed)  
Process snapshot: `docs/ops/2026-09-16-mac-terminal-process-present.json`  
`gh` auth: OK. Operator still must authorize SSH key or run live gate on
Exness host. Do not invent Gate C PASS.
