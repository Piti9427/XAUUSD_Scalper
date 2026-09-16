#!/usr/bin/env bash
# Local evidence before GitHub issue closes (does not replace live #1 gates).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY=python3
fi

echo "==> Unit suite"
"$PY" -m unittest discover -s tests -q

echo "==> Issue #3 mechanical contract"
"$PY" -m unittest tests.test_s1_s4_mechanical_spec_contract -q

echo "==> Broker identity smoke (infra only on Mac without MT5)"
"$PY" scripts/smoke_broker_identity.py | "$PY" -c "import sys,json; d=json.load(sys.stdin); assert 'infra_verdict' in d"

echo "OK: in-repo software gates for #3/#4; live #1 still needs Exness/Oracle/Demo evidence."
