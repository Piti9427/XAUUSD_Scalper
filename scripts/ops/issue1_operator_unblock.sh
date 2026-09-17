#!/usr/bin/env bash
# Issue #1 operator unblock — print exact next steps. Does NOT invent Gate C PASS.
# Safe: prints pubkey path/content for authorization only; no SSH login attempts.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "==> Issue #1 status (open until live Gates C/D)"
echo "    Tracker: only #1 open; #2/#3/#4 closed"
echo "    Mac software Gate B: scenarios 1–23 covered"
echo "    Live Gate C/D: blocked on this Mac (Wine IPC -6 / no Exness session)"
echo ""

echo "==> 1) Prefer: run live gate ON the MT5 host (Windows / Oracle with Exness Demo hedging)"
echo "    cd $ROOT"
echo "    export MT5_TERMINAL_PATH='C:\\Program Files\\MetaTrader 5\\terminal64.exe'  # if needed"
echo "    export XAUUSD_MT5_LOGIN='<demo_login>'"
echo "    export XAUUSD_MT5_PASSWORD='<demo_password>'"
echo "    export XAUUSD_MT5_SERVER='Exness-MT5Trial'   # exact server string from Exness"
echo "    ./scripts/ops/foundation_live_gate.sh"
echo "    Expect: docs/ops/<date>-exness-smoke.json with ok:true"
echo "    Smoke reads the same env vars (never writes password into JSON)."
echo ""
echo "==> 1b) Mac Wine alone is NOT enough today"
echo "    - terminal64 may run, but Wine Python initialize is still -6 Authorization failed"
echo "    - Wine prefix has zero Exness configs (see docs/ops/2026-09-16-mac-wine-exness-prefix-hunt.json)"
echo "    - Logging into Exness in the GUI does not clear Gate C until smoke ok:true exists"
echo "    - Quick Mac probe (expect ok:false here): python3 scripts/ops/issue1_mac_gate_c_probe.py"
echo ""

echo "==> 1c) MacBook-only (no Windows PC): use UTM Windows VM on this Mac"
echo "    UTM.app is present but zero .utm VMs found on this host."
echo "    Steps:"
echo "      1. UTM → New → Windows 11 (ARM if Apple Silicon)"
echo "      2. Inside VM: install Exness MT5 + Python + pip install MetaTrader5"
echo "      3. Copy/clone this repo into the VM"
echo "      4. export XAUUSD_MT5_LOGIN / PASSWORD / SERVER=Exness-MT5Trial"
echo "      5. ./scripts/ops/foundation_live_gate.sh  → expect ok:true smoke JSON"
echo "    Evidence note: docs/ops/2026-09-17-macbook-only-gate-c-path.json"
echo "    Wine MetaQuotes on Mac is NOT a substitute (server=MetaQuotes-Demo, IPC -6)."
echo ""

echo "==> 2) Or: authorize this Mac SSH key on that host, then re-run from here"
echo "    Note: Cursor agent sandbox often cannot open outbound :22 (see"
echo "    docs/ops/2026-09-17-host-ssh-agent-sandbox-denied.json). Run SSH from"
echo "    your own terminal after authorized_keys is updated."
PUB="${HOME}/.ssh/id_ed25519.pub"
if [[ -f "$PUB" ]]; then
  echo "    Pubkey file: $PUB"
  echo "    Pubkey:"
  echo "    $(cat "$PUB")"
  echo "    Append to authorized_keys for the MT5 SSH user, then:"
  echo "    ssh <user>@<host> 'cd <repo> && ./scripts/ops/foundation_live_gate.sh'"
else
  echo "    (no ~/.ssh/id_ed25519.pub — generate one or supply alternate identity)"
fi
echo ""

echo "==> 3) After smoke ok:true, still required before closing #1"
echo "    - Oracle soak: copy docs/ops/oracle-soak-result.template.json → docs/ops/<date>-oracle-soak.json"
echo "      set completed=true + infra_status + host (never invent PASS_INFRA)"
echo "    - Demo 12w: copy docs/ops/demo-12w-start.template.json → docs/ops/<date>-demo-12w-start.json"
echo "      set started=true + start_utc + rule_commit_sha + account identity"
echo "    - Refresh: python3 scripts/ops/issue1_live_gate_readiness.py  (issue1_closable must become true)"
echo ""

echo "==> Current readiness snapshot"
python3 scripts/ops/issue1_live_gate_readiness.py || true
echo ""
echo "Do NOT close GitHub #1 until issue1_closable is true with real artifacts."
