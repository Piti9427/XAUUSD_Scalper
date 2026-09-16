#!/usr/bin/env bash
# Issue #1 live gate helper — run on a host with MT5 + Exness Demo (hedging) session.
# Mac native / Wine IPC is INCONCLUSIVE_INFRA — use Windows or proven Oracle stack.
# Optional: export MT5_TERMINAL_PATH=C:\\Program Files\\MetaTrader 5\\terminal64.exe
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
DATE_TAG="$(date -u +%Y-%m-%d)"
OUT="docs/ops/${DATE_TAG}-exness-smoke.json"

SMOKE_ARGS=(--out "$OUT")
if [[ -n "${MT5_TERMINAL_PATH:-}" ]]; then
  SMOKE_ARGS+=(--path "$MT5_TERMINAL_PATH")
fi
if [[ -n "${1:-}" ]]; then
  SMOKE_ARGS+=(--path "$1")
fi

echo "==> Broker identity + hedging mode smoke (no orders)"
python3 scripts/smoke_broker_identity.py "${SMOKE_ARGS[@]}"
cat "$OUT"

echo ""
echo "==> After smoke ok:true, also verify:"
echo "    - Webhook /internal/clock reconciles uncertain intents + ROLLOVER 20:55 + TIME_EXIT"
echo "    - Cron: scripts/ops/webhook-clock-cron.example.sh"
echo ""
echo "==> Remaining manual gates:"
echo "    - Oracle ARM64 soak: docs/ops/2026-09-16-oracle-arm64-runtime-checklist.md"
echo "    - Forward Demo 12w: docs/ops/2026-09-16-foundation-demo-12w-protocol.md"
echo ""
echo "Tracker: #2/#3/#4 already closed. Do NOT close #1 until smoke ok:true + soak + Demo start evidence."
