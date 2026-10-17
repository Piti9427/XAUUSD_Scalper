#!/usr/bin/env bash
# Interactive unblock for GitHub write + push (Issue tracker close path).
# Run in a local Terminal.app / iTerm session (needs GUI keychain + browser).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Unlock login keychain (prompt)"
security unlock-keychain ~/Library/Keychains/login.keychain-db || true

if ! gh auth status -h github.com >/dev/null 2>&1; then
  echo "==> gh token invalid/missing — interactive login (browser)"
  # Prefer HTTPS + repo scope so issue close + push both work.
  gh auth login -h github.com -p https -s repo,read:org --web
else
  echo "==> Refresh gh with repo scope (browser)"
  gh auth refresh -h github.com -s repo || {
    echo "==> refresh failed — falling back to full login"
    gh auth login -h github.com -p https -s repo,read:org --web
  }
fi

echo "==> Verify scopes"
gh auth status
# Prefer git credential from gh (avoids stale osxkeychain -25293).
gh auth setup-git

echo "==> Optional SSH fallback (if HTTPS push still fails)"
if [[ -f "$HOME/.ssh/id_ed25519" ]]; then
  ssh-add --apple-use-keychain "$HOME/.ssh/id_ed25519" 2>/dev/null \
    || ssh-add "$HOME/.ssh/id_ed25519" 2>/dev/null \
    || true
fi
if [[ -f "$HOME/.ssh/id_ed25519.pub" ]]; then
  echo "    Public key (add at https://github.com/settings/keys if SSH auth fails):"
  cat "$HOME/.ssh/id_ed25519.pub"
  echo "    Then: git remote set-url origin git@github.com:Piti9427/XAUUSD_Scalper.git && git push -u origin HEAD"
fi

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
- tests/application/test_s1_s4_mechanical_spec_contract.py
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
