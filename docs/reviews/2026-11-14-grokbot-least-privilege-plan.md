# Grokbot VM access — least-privilege plan (2026-11-14)

Status: **PLAN ONLY — nothing applied.** Every VM step needs owner approval at execution time.
Refs: SEC-1/SEC-4 in `2026-11-13-c22-security-best-practices-report.md`, I8 in `2026-11-13-c22-vm-open-issues-diagnosis.md`.

## 1. Evidence (read-only, VM journal, last 7 days)

Key `grokbot-vm-oracle` (`SHA256:v48ocAXjPqxt//aNKI/noCo2gd/2E5gHkQkW0AH9lDk`) logs in as `ubuntu` (`NOPASSWD: ALL`).
SSH sessions: grokbot **1,694** vs other keys 81. Sudo commands mapped to grokbot sessions (via `_AUDIT_SESSION`), 424 total:

| Kind | Commands (count) |
|---|---|
| Monitor (read) | `ss -tnp state established '( dport = :443 )'` 147 · `ops-local/mt5_ap_lock.sh status` 144 · `tail`/`awk` `state/mt5-ap-watchdog.log` 24 · `journalctl -u c22-selected-execution …` ~45 · `journalctl -u mt5-ap-watchdog` 2 · `iptables -S MT5_AP_LOCK` 3 |
| **Operator (write)** | 2026-11-10 05:13–05:28 deploy: `systemctl stop/start c22-selected-execution`, `daemon-reload` · 2026-11-12 03:23/03:36 install `/usr/local/bin/c22-trade-notify` + unit, restart · 2026-11-12 07:13 and **08:14:35** sender stop/start (= current cost-review acceptance) |
| Unknown (root code) | `sudo python3 -` ×5: arbitrary root code, purpose unknown. Treat as ops; expect denial under c22mon, investigate, do **not** widen the wrapper for it |
| Non-sudo | `extract_remote.py` reads **live** sqlite journal (I8, 2026-11-13 01:22Z) |

Conclusion: grokbot is the **monitor and the deploy/renewal operator**. If its access is cut to read-only in one step, deploys and the I4 cost-review renewal (due by 2026-11-19 08:14:35 UTC) stop working.
The plan below therefore **separates the two roles**:
- The high-frequency monitor loop (~240 sessions/day from rotating cloud IPs) moves to a new non-root identity.
- The root-capable ops key stays until the owner decides its future, after the renewal.

Other VM facts relevant to the plan:
- `/home/ubuntu` is mode 750 and `state/` is 700.
- `setfacl` is not installed.
- The `systemd-journal` group exists and is empty.
- sshd has `PasswordAuthentication no`.
- `ops-local/mt5_ap_lock.sh` is `ubuntu:ubuntu` mode 775 and runs as root via sudo. Its directory `c22-demo/` is ubuntu-writable 775, so a chown alone does not fix that SEC finding. It is **out of scope here**; c22mon cannot write it (not in group `ubuntu`), so calling it via the wrapper gives c22mon no escalation.
- Source IPs (14 d, 32 distinct): whois puts all of them on Amazon (23 Amazon Technologies Inc., 9 Amazon.com Inc.; 77.112/77.113 are AMAZO-4 via ARIN). This is consistent with bot cloud egress, with no residential or foreign-ISP outlier.
- Backups live in `/home/ubuntu/c22-demo/backups/selected-execution` (daily at 21:50 UTC).

## 2. Target state

| Identity | Key | Can | Cannot |
|---|---|---|---|
| `c22mon` (new) | **new** key generated on the grok side, `restrict` | read journald (group `systemd-journal`), run `sudo /usr/local/sbin/c22mon <fixed-subcommand>` | sudo anything else, read `state/` or the live DB, write to `/home/ubuntu`, have a pty or forwarding |
| `ubuntu` | Mac key (unchanged) and grokbot ops key (unchanged until Phase 3) | everything, as today | — |

Wrapper `/usr/local/sbin/c22mon` (root:root 0755, no free arguments, `case` on a fixed list):
- `net`: runs `ss -tnp state established '( dport = :443 )'`, `ss -tnpH state all` and `iptables -S MT5_AP_LOCK`.
- `aplock`: runs `mt5_ap_lock.sh status`.
- `aplog`: runs `tail -n 40` on `state/mt5-ap-watchdog.log`.
- `snapshot`: copies the **newest completed backup file** from `backups/selected-execution` to `/home/c22mon/snap/journal.sqlite3`, chowns it to c22mon and prints its sha256. It never touches the live DB.
  - Before writing this, check the exact filename and manifest format against `backup.py` 8de9 during implementation.
- Anything else exits 2.

Sudoers drop-in `/etc/sudoers.d/60-c22mon` (0440):
```
c22mon ALL=(root) NOPASSWD: /usr/local/sbin/c22mon net, /usr/local/sbin/c22mon aplock, /usr/local/sbin/c22mon aplog, /usr/local/sbin/c22mon snapshot
```
`journalctl -u <unit>` needs no sudo once c22mon is in `systemd-journal`. Note: that group reads **all** units' logs, including other users' sudo command lines. These are not secret values today, but this is a known read scope.

Trading impact: **none**.
- No change to the sender, terminal, watchdog, backup units or release tree.
- No restart.
- No position or risk-control change.

## 3. Phases

### P0 — owner, no VM change
1. Match the fingerprint above against the key configured in the Grok bot.
2. Generate a **second** key pair on the grok side for monitoring, and send only its public key.
3. Decide on the ops role after the renewal (P3): option A or B.

### P1 — VM setup (approval needed, about 15 min, no service touched)
1. Preflight, read-only:
   - `ls backups/selected-execution`, to fix the snapshot filename logic.
   - Confirm that `mt5_ap_lock.sh status` is read-only (it only lists rules).
2. (removed; the mt5_ap_lock.sh ownership and directory fix is a separate item, because it touches the live AP-lock unit.)
3. `sudo useradd -m -s /bin/bash -G systemd-journal c22mon`. Do not add it to sudo, adm or lxd, and set no password.
4. `/home/c22mon/.ssh/authorized_keys` 0600: `restrict ssh-ed25519 <NEW_PUB> grokbot-monitor`.
5. Install the wrapper, then the sudoers drop-in through `visudo -cf` before moving it into place.
6. Verify as c22mon from the Mac (the owner temporarily adds the Mac pubkey or uses `sudo -u c22mon`):
   - `sudo -n true` → denied.
   - `sudo -l` → only the 4 entries.
   - `ls /home/ubuntu/c22-demo/state` → denied.
   - `journalctl -u c22-selected-execution -n 5` → OK.
   - Each wrapper subcommand → OK.
   - An unknown subcommand → exit 2.

### P2 — switch grokbot's monitor jobs (owner-side config, 24 h observe)
1. Point Grok's monitoring and journal-extractor jobs at `c22mon@158.178.243.98` with the new key.
2. Point the extractor at `/home/c22mon/snap/journal.sqlite3`, refreshed with `sudo c22mon snapshot`. This fixes I8: no more SHARED lock on the live DB.
   - The data is up to 24 h old (daily backup). If fresher data is needed, decide separately. Never reopen the live DB.
3. Observe for 24 h:
   - **Pass criterion:** zero grokbot-key `ubuntu` sessions outside an owner-approved window. Any such session means the separation failed, because the bot fell back to the root key. In that case stop and apply P3-A step 1 immediately.
   - Expected denial to investigate: `sudo python3 -`.
   - c22mon sessions should carry the monitor load.
   - No `sudo` denials should appear for needed commands. If one appears, extend the wrapper and do not grant broad sudo.

### P3 — ops key (owner decision, **after the I4 renewal is done**)
An LLM monitor that gets a sudo denial will try any key that still works. Unless the root key is out of the routine bot's reach, P2 gains nothing.
- **A (keep, default):**
  1. Keep the grokbot ops key in a separate bot config or profile that the monitoring jobs cannot use.
  2. Keep the `~ubuntu/.ssh/authorized_keys` grokbot line **commented out by default**. The owner enables it only for an approved deploy or renewal window and disables it afterwards.
  - Narrowing its sudo is not worth it: `install` + `daemon-reload` already equal root.
- **B (remove):** delete the grokbot line from `~ubuntu/.ssh/authorized_keys`, and run all deploys and renewals from the Mac key (do SEC-3 passphrase first).
  - Stronger, but the renewal and deploy runbooks must then run from the Mac.

## 4. Rollback
- P1: `userdel -r c22mon`, `rm /etc/sudoers.d/60-c22mon /usr/local/sbin/c22mon`.
- The ubuntu account and the Mac key are untouched throughout, so there is no lockout risk. OCI console is the last resort.
- P2: point the Grok jobs back at the old key. Nothing on the VM changes.

## 5. Not covered / open
- The Grok host's own security (where the keys are stored, who can trigger the bot). It is outside the VM.
- Whether the Grok monitor needs data fresher than the daily backup.
- `ubuntu` keeps `NOPASSWD: ALL` and `lxd` (SEC-4). That is a separate, larger change.
- The ops key's 32 source IPs (all AWS) rotate, so `from=` is not usable. An AWS-wide range would be meaningless.

## P1 applied 2026-11-17 (owner approved "ทำ P1 ต่อ")
- **User.** `c22mon` (uid 1003): groups `c22mon` and `systemd-journal` only, with no sudo, adm or lxd. Its password is locked, and `/home/c22mon/.ssh/authorized_keys` (0600) is **empty**, waiting for the P0 public key.
- **Wrapper.** `/usr/local/sbin/c22mon` is root:root 0755, with subcommands net, aplock, aplog and snapshot. aplock points at `/usr/local/sbin/mt5_ap_lock.sh` (SEC-8). snapshot copies the newest backup whose manifest has `restore_verified=true`. Source: `runs/c22-security-b-grokbot-2026-11-17/c22mon`, sha256 `64af9a72…`.
- **Sudoers.** `/etc/sudoers.d/60-c22mon` is mode 0440 and passed `visudo -c`.
- **sshd.** `AllowUsers ubuntu c22mon`, plus `Match User c22mon` with AllowTcpForwarding no, PermitTTY no and X11Forwarding no. `sshd -t` passed, the service was reloaded, and a fresh `ubuntu` login was verified. ubuntu keeps PermitTTY and TCP forwarding, so Grokbot ops are unchanged.
- **Verified as c22mon:**

  | Check | Result |
  | --- | --- |
  | `sudo true` | denied |
  | `sudo bash` | denied |
  | unknown subcommand | denied by sudo |
  | extra argument | denied |
  | `state/` and the live DB | permission denied |
  | journalctl | OK |
  | net, aplock, aplog | OK |
  | snapshot | OK; sha 5b6d4b18… matches the manifest, and the read-only sqlite opens |

- Sender is active with NRestarts 0.
- **Next steps (owner):**
  - P0: send the new monitor public key. It is installed as `restrict ssh-ed25519 … grokbot-monitor`.
  - P2: point the bot's monitor and extractor at `c22mon@` and `/home/c22mon/snap/journal.sqlite3`.
  - The ops key stays as-is, so deploys and renewals via the bot keep working.
- **Rollback:**
  1. `userdel -r c22mon`
  2. `rm /etc/sudoers.d/60-c22mon /usr/local/sbin/c22mon`
  3. Remove `c22mon` and the Match block from `50-c22-hardening.conf`, then run `sshd -t` and reload. A backup is at `/root/50-c22-hardening.conf.bak-*`.
