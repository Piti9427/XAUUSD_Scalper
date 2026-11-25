# VM snapshot 2026-11-17 (SEC-5 / SEC-14)

This is a read-only copy of what was running on the Oracle VM on 2026-11-17 at about 12:00 UTC, taken after cost renewal v4. Nothing here is deployed from the repo.

- `release/selected-23ab6655adee8443/`: the exact live sender release.
  - `release.sha256` checks out: 88/88 OK.
  - Excluded: the `data` symlink and `__pycache__`.
  - Its sha256 values are the off-VM anchor for SEC-7 drift checks.
- `vm-tooling/`:
  - `/usr/local/bin/c22-trade-notify`;
  - the `ops-local/mt5_ap_*.sh` scripts;
  - the c22/mt5 systemd units and drop-ins, without `.bak` files.
- `SNAPSHOT.sha256`: sha256 of every file here.
- No secrets. Env files, `c22-private/` and `demo-account.json` were not copied. The units carry only empty `DEMO_TELEGRAM_*=` placeholders.
- Not captured: the VM runtime-venv hash-pinned requirements file, which was not found at `runtime-venv/requirements.txt` (SEC-20 open).

**Verify against the VM later** (read-only):

```bash
ssh ... 'cd /home/ubuntu/c22-demo/releases/selected-23ab6655adee8443 && sha256sum -c release.sha256'
```

Compare `release.sha256` byte-for-byte with this copy.
