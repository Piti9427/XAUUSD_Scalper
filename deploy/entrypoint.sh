#!/bin/bash
set -e

# Start virtual display buffer for Wine / GUI emulation
echo "Starting Xvfb on :99..."
Xvfb :99 -screen 0 1024x768x16 &
XVFB_PID=$!

# Trap termination signals to shut down gracefully
trap "echo 'Stopping container...'; kill -TERM $XVFB_PID 2>/dev/null || true; exit 0" SIGINT SIGTERM

echo "Starting XAUUSD SMC v1 Copilot daemon..."
exec python3 smc_main.py
