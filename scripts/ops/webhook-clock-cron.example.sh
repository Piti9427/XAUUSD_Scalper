#!/usr/bin/env bash
# Example: periodic broker lifecycle + TIME_EXIT reconciler (Issue #1 Gate C).
# Install via cron/systemd on the host running run_staging_bridge.py.
set -euo pipefail
WEBHOOK_URL="${WEBHOOK_URL:-http://127.0.0.1:8000/internal/clock}"
WEBHOOK_SECRET="${WEBHOOK_SECRET:?export WEBHOOK_SECRET from config/settings.yaml or env}"
curl -fsS -X POST "$WEBHOOK_URL" \
  -H "Authorization: Bearer ${WEBHOOK_SECRET}" \
  -H "Content-Type: application/json"
