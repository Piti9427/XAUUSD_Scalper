#!/usr/bin/env bash
# Issue #1 live gate helper — run on a host with MT5 + Exness Demo session.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
DATE_TAG="$(date -u +%Y-%m-%d)"
OUT="docs/ops/${DATE_TAG}-exness-smoke.json"

echo "==> Broker identity smoke (no orders)"
python3 scripts/smoke_broker_identity.py --out "$OUT"
cat "$OUT"

echo ""
echo "==> Remaining manual gates (see docs/ops/2026-09-16-oracle-arm64-runtime-checklist.md):"
echo "    - Oracle ARM64 soak evidence"
echo "    - Forward Demo 12w per docs/ops/2026-09-16-foundation-demo-12w-protocol.md"
echo ""
echo "After push auth works: ./scripts/ops_unblock_github.sh closes #3/#4/#2 only."
