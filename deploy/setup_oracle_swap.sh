#!/bin/bash
# ==============================================================================
# Oracle Cloud Free Tier (1GB RAM) - 4GB Swap Space Configuration Script
# Prevents Out-Of-Memory (OOM) killer from terminating MT5 / Wine / Python daemon.
# Idempotent: Safely skips if /swapfile is already active.
# ==============================================================================

set -euo pipefail

SWAP_FILE="/swapfile"
SWAP_SIZE="4G"

echo "=== [1/5] Checking existing swap configuration ==="
if swapon --show | grep -q "${SWAP_FILE}"; then
    echo ">> Swapfile ${SWAP_FILE} is already active. Current status:"
    swapon --show
    free -h
    echo ">> Nothing to do. Exiting safely."
    exit 0
fi

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (or with sudo)." >&2
    exit 1
fi

echo "=== [2/5] Allocating ${SWAP_SIZE} swapfile ==="
if command -v fallocate >/dev/null 2>&1; then
    fallocate -l "${SWAP_SIZE}" "${SWAP_FILE}" || dd if=/dev/zero of="${SWAP_FILE}" bs=1M count=4096 status=progress
else
    dd if=/dev/zero of="${SWAP_FILE}" bs=1M count=4096 status=progress
fi

echo "=== [3/5] Setting secure permissions and formatting ==="
chmod 600 "${SWAP_FILE}"
mkswap "${SWAP_FILE}"
swapon "${SWAP_FILE}"

echo "=== [4/5] Making swap persistent across reboots in /etc/fstab ==="
if ! grep -q "${SWAP_FILE} none swap sw 0 0" /etc/fstab; then
    echo "${SWAP_FILE} none swap sw 0 0" >> /etc/fstab
    echo ">> Appended swap entry to /etc/fstab."
fi

echo "=== [5/5] Tuning swappiness and cache pressure for low-RAM VM ==="
# Swappiness 10 means swap only when memory is genuinely constrained
sysctl vm.swappiness=10
sysctl vm.vfs_cache_pressure=50

mkdir -p /etc/sysctl.d
cat <<EOF > /etc/sysctl.d/99-xauusd-swap.conf
vm.swappiness=10
vm.vfs_cache_pressure=50
EOF

echo "=============================================================================="
echo "Swap configuration successful!"
free -h
echo "=============================================================================="
