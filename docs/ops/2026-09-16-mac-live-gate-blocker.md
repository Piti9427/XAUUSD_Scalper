# Mac host live-gate probe (Issue #1)

**Host:** macOS (darwin) development machine  
**Captured:** 2026-09-16  
**Verdict:** `INCONCLUSIVE_INFRA` — cannot close Gate C identity smoke from this Mac alone

## Native macOS Python

Command:
```bash
.venv/bin/python scripts/smoke_broker_identity.py --out docs/ops/2026-09-16-mac-native-smoke.json
```

Result: `mt5_import_missing` → `infra_verdict=INCONCLUSIVE_INFRA`  
Reason: official `MetaTrader5` wheel is Windows-only; Mac `.venv` cannot import it.

Artifact: `docs/ops/2026-09-16-mac-native-smoke.json`

## Mac MetaTrader 5.app (Wine prefix) + Windows Python probe

Installed embeddable CPython 3.12 + `MetaTrader5==5.0.6180` inside the MetaQuotes Wine prefix and probed initialize while `terminal64.exe` was running.

| Attempt | Result |
| --- | --- |
| `mt5.initialize()` | `False` `(-10003, 'IPC initialize failed, MetaTrader 5 x64 not found')` |
| `mt5.initialize(path=terminal64.exe)` | `False` `(-6, 'Terminal: Authorization failed')` |

Interpretation:
- Explicit `path=` moves Mac Wine from IPC-not-found to auth failure (progress, not PASS).
- Wine terminal `common.ini` shows **MetaQuotes-Demo** (not Exness). No Exness MT5 install found on this Mac.
- Smoke CLI now accepts `--path` / `MT5_TERMINAL_PATH` (`scripts/smc/mt5_init.py`).

Do **not** treat MetaQuotes Wine as Gate C PASS.

Artifacts: `docs/ops/2026-09-16-mac-wine-initialize-path.json`, `docs/ops/2026-09-16-mac-wine-auth-retry.json`

## Still required for #1 close (not possible as pure Mac-dev work)

1. Host with working MT5 Python IPC (Windows native, or Oracle ARM64 stack that actually binds) logged into **Exness Standard Demo**
2. `python scripts/smoke_broker_identity.py --out docs/ops/<date>-exness-smoke.json` with `ok: true`
3. Oracle ARM64 soak evidence per `docs/ops/2026-09-16-oracle-arm64-runtime-checklist.md`
4. Forward Demo 12w start per `docs/ops/2026-09-16-foundation-demo-12w-protocol.md`

Helper on a capable host: `./scripts/ops/foundation_live_gate.sh`
