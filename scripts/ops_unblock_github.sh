#!/usr/bin/env bash
# Interactive unblock for GitHub write + push (Issue tracker close path).
# Run in a local Terminal.app / iTerm session (needs GUI keychain + browser).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Unlock login keychain (prompt)"
security unlock-keychain ~/Library/Keychains/login.keychain-db

echo "==> Refresh gh with repo scope (browser)"
gh auth refresh -h github.com -s repo

echo "==> Verify scopes"
gh auth status

echo "==> Local software gate audit (optional)"
if [[ -x "$ROOT/scripts/audit_local_issue_gates.sh" ]]; then
  "$ROOT/scripts/audit_local_issue_gates.sh"
fi

echo "==> Push feature/smc-v2-hardening"
git push -u origin feature/smc-v2-hardening

echo "==> Close evidence JSON (paste into issue comments if helpful)"
python3 "$ROOT/scripts/generate_close_evidence.py" | tee "$ROOT/docs/ops/$(date -u +%Y-%m-%d)-github-close-evidence.json"

echo "==> Close #3 (mechanical spec)"
gh issue close 3 -R Piti9427/XAUUSD_Scalper --reason completed --comment "$(cat <<'EOF'
Mechanical v1 deliverable landed in-repo.

Evidence:
- docs/specs/xauusd-s1-s4-mechanical-v1.md
- tests/test_s1_s4_mechanical_spec_contract.py
- docs/handoff/2026-09-16-issues-3-4-local-acceptance-audit.md
- branch feature/smc-v2-hardening
EOF
)"

echo "==> Close #4 (research handoff)"
gh issue close 4 -R Piti9427/XAUUSD_Scalper --reason completed --comment "$(cat <<'EOF'
Research handoff v1 published.

Evidence:
- docs/specs/xauusd-s1-s4-research-handoff-v1.md
- Explicit Gate B/C blockers listed
- docs/handoff/2026-09-16-issues-3-4-local-acceptance-audit.md

Live/runtime evidence remains under #1.
EOF
)"

echo "==> Close #2 (parent) after children"
gh issue close 2 -R Piti9427/XAUUSD_Scalper --reason completed --comment "$(cat <<'EOF'
Children #3/#4 documentation deliverables are complete in-repo.
Closing parent tracker item; Gate A freeze / experiment start remains a
separate operator decision under the research handoff + foundation gates.
EOF
)"

echo "==> Reminder: do NOT close #1 until Exness smoke + Oracle soak + Demo 12w evidence exist."
gh issue list -R Piti9427/XAUUSD_Scalper --state open
