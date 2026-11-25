# C22 Selected26b8 Demo — Security best-practices report (2026-11-13)

Scope: Oracle VM `158.178.243.98` (host, units, ops tooling, secrets handling) + live Python path
(`scripts/c22_selected`, `scripts/demo_runtime`, `scripts/ops` in release `selected-23ab6655adee8443`)
+ legacy FastAPI webhook (`scripts/webhook`, `scripts/webhook_bridge.py`).
Method: 5 read-only review agents (host, secrets, code, integrity, webhook) + 1 independent skeptic each
(re-ran evidence, adjusted severity). Reference: skill `python-fastapi-web-server-security.md` (webhook only;
live path has no web server). No secret values were read into this report; all values `<REDACTED>`.
Threat model: single-owner Demo account (real money prohibited), but the VM holds real credentials and root.

## Executive summary

Live trading code is clean: parameterised SQL, list-form subprocess, no pickle/yaml.load/eval, strict
`request_id` regex, 0600 files, process umask 0077, Demo identity checked before every `order_send`.
Risk sits in **access & host**: everything runs as `ubuntu`, which has `NOPASSWD: ALL` sudo, and two SSH keys
without restrictions reach it — one is an unconfirmed assistant-box key that is the most active login, the
other has no passphrase on the Mac. The VM also co-hosts an unrelated **public Next.js site** run by a second
sudo-group user. Fixing access (confirm/restrict keys, passphrase, separate web app) removes most of the risk;
no finding requires touching the sender release.

## High

**SEC-1 — `grokbot-vm-oracle` monitor key = unrestricted passwordless root, most active login** (owner-confirmed 2026-11-14 → Medium)
- `/home/ubuntu/.ssh/authorized_keys` line 2 (ED25519 `SHA256:v48ocAX…`), no `from=`/`restrict`/`command=`;
  `/etc/sudoers.d/90-cloud-init-users` `ubuntu ALL=(ALL) NOPASSWD:ALL`; ubuntu also in `lxd`.
- 14 days: ≈3,011 logins from 24 IPs (first 2026-11-01 12:29, same mtime as authorized_keys) vs ≈451 for the owner key.
- Impact: whoever holds that key (or compromises the host it lives on) has immediate root and the MT5 Demo password.
- Severity: High until ownership is confirmed (reviewers rated low/medium/high; skeptic for integrity kept High).
  If owner confirms it is the assistant box → Medium.
- Fix: owner confirms fingerprint. Then move it to a dedicated non-sudo, non-lxd user (`assistant`) with
  `restrict` (+ `from="<egress IP>"` if stable) and narrow read-only sudoers (journalctl, systemctl show/status) if needed.
  If not confirmed → remove the key. Trading regression: none (test new access from that host before closing session).
- **Owner update 2026-11-14:** owner states the key belongs to their Grok bot that monitors the VM → legitimate
  access, re-rated **Medium** (least-privilege gap, not an intrusion). Fingerprint not yet matched against the bot's
  configured key — do that once. 14 d source IPs: 32, all Amazon per whois → cloud egress, `from=` not usable.
  Journal evidence: the bot is **also the operator**. It ran the 2026-11-10 deploy, the 11-12 trade-notify installs,
  the 11-12 08:14:35 sender stop/start (current cost-review acceptance) and `sudo python3 -` ×5. A one-step
  read-only lockdown would break deploys and the I4 renewal. Plan: split the roles (new non-root `c22mon` for monitoring,
  extractor on a backup snapshot instead of the live DB; ops key out of the routine bot's reach) →
  `2026-11-14-grokbot-least-privilege-plan.md`.

## Medium

**SEC-2 — Public Next.js app co-hosted on the trading VM, run by a sudo-group user**
- `pm2-piti.service` (User=piti) → `next-server v16.2.9` on `*:3000`, nginx public 80/443 (`sites-enabled/nop-project:7`
  `proxy_pass http://127.0.0.1:3000`). `piti` ∈ sudo, password set; unit has NoNewPrivileges=no, ProtectSystem=no.
- Impact: web-app RCE → local shell on the box holding MT5 credentials; sudo via piti's password or local kernel bug.
- Fix: smallest — `gpasswd -d piti sudo`, bind Next to 127.0.0.1, add NoNewPrivileges/ProtectSystem=strict to pm2-piti.
  Best — move the site to its own instance. No trading impact.

**SEC-3 — VM SSH private key on the Mac has no passphrase**
- `~/ssh-keys/ssh-key-2026-06-16.key` (RSA 2048, `SHA256:iSuYpR…`): `ssh-keygen -y -P ""` succeeds; dir `~/ssh-keys` 0755.
- Impact: any Mac compromise / backup leak of that file = root on VM.
- Fix (Mac only): `ssh-keygen -p -f ~/ssh-keys/ssh-key-2026-06-16.key`, `ssh-add --apple-use-keychain`, `chmod 700 ~/ssh-keys`.
  Automation keeps working through the agent. Consider ED25519 rotation later.

**SEC-4 — All bot services run as `ubuntu`, which is passwordless root**
- execution/terminal/watchdog/backup/trade-notify units: `User=ubuntu`; sandboxing mostly off
  (`systemd-analyze security` ≈9.0 except trade-notify 8.4). NoNewPrivileges blocks sudo *inside* units, but
  any ubuntu-level foothold (SSH key, closed-source MT5 binary under Wine, dependency) = root, and all integrity
  controls (release.sha256, review JSON, firewall script) are advisory against ubuntu.
- Fix (owner decision, staged): require password for ubuntu sudo or move admin to a separate account after reviewing
  what go-deploy scripts need; drop `lxd`. Longer term dedicated service uid for terminal/sender. Do not change the
  live units without a staging rehearsal (Wine prefix/state paths must stay writable).

**SEC-5 — Live sender code has no source-control provenance**
- 9 of 30 hashed core files in the VM release match no commit/worktree: `c22_selected/execution.py`, `trial_costs.py`;
  `demo_runtime/backup.py`, `boundary.py`, `broker.py`, `costs.py`, `diagnostics.py`, `journal.py`, `lifecycle.py`.
- Impact: tampering or loss cannot be detected/reconstructed off-VM; ties to issue I7 (3-way merge needed).
- Fix: scp the exact VM files read-only into a branch, commit as "deployed selected-23ab6655adee8443", record commit +
  `sha256(release.sha256)` per release; build future releases from `git archive <sha>`.

## Low

| ID | Finding | Location | Fix (all VM changes need owner approval) |
|---|---|---|---|
| SEC-6 | New kernel 7.0.0-1016 installed, running 1013; reboot pending | `/var/run/reboot-required` (11-13 06:02) | Reboot in a flat, market-closed window with boot-recovery checks; no auto-reboot |
| SEC-7 | `release.sha256` is drift detection only: self-held, ubuntu-writable (0664), misses `__pycache__` (65 pyc written at runtime) and EnvironmentFile/Wine binaries | `ExecStartPre sha256sum --check`; `prepare-release.sh:26-28` | Keep; add off-VM anchor (SEC-5); `PYTHONDONTWRITEBYTECODE=1` at next flat restart; record hashes of env file/Wine/python off-VM |
| SEC-8 | Root-run firewall script owned by ubuntu, group-writable | `mt5-ap-lock.service` → `ops-local/mt5_ap_lock.sh` 775 | Copy to `/usr/local/sbin` root:root 755, repoint unit, commit to repo |
| SEC-9 | `c22-trade-notify` follows redirects and forwards the auth header | `/usr/local/bin/c22-trade-notify:217-232` (plain `urlopen`) | Opener with redirect handler returning None; assert `https` scheme |
| SEC-10 | Webhook secrets readable via notifier `/proc/<pid>/environ` (unit User=ubuntu), so root-only `/etc/c22-trade-notify.env` gives no isolation | `c22-trade-notify.service` | `DynamicUser=yes` or dedicated uid + read-only journal access |
| SEC-11 | sshd: X11/agent/TCP forwarding on, no AllowUsers, MaxAuthTries 6; ≈2.9k invalid-user probes/7d | `sshd -T`; `sshd_config:99` | Drop-in `AllowUsers ubuntu`, `X11Forwarding no`, `AllowAgentForwarding no`, `MaxAuthTries 3`; `sshd -t`, reload with 2nd session open |
| SEC-12 | rpcbind on 0.0.0.0/:::111 (ufw blocks; no NFS in fstab) | rpcbind.socket/service | `systemctl disable --now rpcbind.socket rpcbind.service` |
| SEC-13 | nginx http-level `ssl_protocols` includes TLSv1/1.1 | `/etc/nginx/nginx.conf:33` | `TLSv1.2 TLSv1.3`, `server_tokens off`, `nginx -t` |
| SEC-14 | VM ops tooling untracked/unhashed (`c22-trade-notify` sha256 `ff6507f7…`, `ops-local/*`) | `/usr/local/bin`, `ops-local/` | Commit to `deploy/vm/`, keep `vm-tooling.sha256`, verify from Mac |
| SEC-15 | Journal backups only on same disk, no offsite/tamper-evident copy | `backups/selected-execution` (7×, ≈9.5G) | Mac scp pull of newest `restore_verified` snapshot + sha256 off-VM (no `oci` CLI on VM → don't just add `--private-bucket`) |
| SEC-16 | Weak systemd sandboxing; `mt5-ap-watchdog` lacks NoNewPrivileges | `systemd-analyze security` | NoNewPrivileges on mt5-ap-watchdog; trial ProtectSystem=strict on watchdog/backup first |
| SEC-17 | Legacy webhook hardcoded fallback secret, pushed to GitHub (4 remote branches), equals local `config/settings.yaml:51` | `scripts/run_staging_bridge.py:57-58`, `webhook_bridge.py:24,159` (commit `375f0ed`) | Treat as burned: rotate, remove defaults, fail closed. Not deployed → no history rewrite needed |
| SEC-18 | `config/settings.yaml` 0644 with non-placeholder secret | Mac repo | `chmod 600` |
| SEC-19 | `.gitignore` misses `*.env`, `*.key`, `*.pem`, `demo-account.json`, `c22-private/` | `.gitignore:19-21` | Add patterns (keep `!.env.example`) |
| SEC-20 | Repo `requirements.txt` unpinned `>=`; VM hash-pinned list not in git | `requirements.txt`; VM `runtime-venv/requirements.txt` | Commit VM hash-pinned list as `deploy/c22-demo/runtime-requirements.txt` |
| SEC-21 | Drop-ins say "PROPOSED - NOT APPLIED" but are loaded | `c22-selected-execution.service.d/20-restart-backoff.conf`, `c22-selected-backup.service.d/20-timeout.conf` | Fix comment/runbook (doc drift) |

## Info

- SEC-22 Order-arming review/cost-policy JSON is unsigned and ubuntu-writable — trust boundary is the ubuntu account (→ SEC-1/3/4). Do **not** weaken the validator.
- SEC-23 Cohort `release_hash` excludes `scripts/smc/account_mode.py`, `mt5_init.py` (identity checks) and `scripts/ops` (`demo_runtime/runner.py:57-63`, `c22_selected/runner.py:88-94`). Add in a future release (new review).
- SEC-24 MT5 Demo password exists in `c22-private/c22-shadow.env` and `demo-account.json` (both 0600, same uid); archive the latter once preparation probes are retired.
- SEC-25 Group-writable dirs under `/home/ubuntu/c22-demo` (775) and interactive umask 0002 — `chmod g-w`, umask 077 for deploy shells.
- SEC-26 Legacy webhook (not deployed anywhere; nothing listens): `auth.py:23` non-constant-time `!=`; OpenAPI docs on + `/health` unauth + `0.0.0.0:8000` (`webhook_bridge.py:56-60,99-114,175`); no body/schema limits (`tradingview_routes.py:26,35`); last-4 of secret logged (`run_staging_bridge.py:84`); bridge can send orders with `dry_run:false` + `allow_demo_only` (`real_money_approval.py:46-47`) — add `LEGACY_BRIDGE_ENABLE=1` guard or mark retired (AGENTS.md one-sender rule).
- SEC-27 Deploy script hygiene: `go-deploy-v3.sh:6` no `-e`; `prepare-release.sh:26-27` predictable `/tmp/c22-release-list.$$` + unquoted `$(cat …)` (mitigated by protected_symlinks).
- SEC-28 Legacy `c22-demo-backup.timer` still snapshots the frozen 10-25 shadow journal daily — disable after final snapshot.
- SEC-29 MT5 terminal egress lock covers only TCP/443 (broker pinning, not exfiltration containment). Localhost listener `127.0.0.1:22346` (wineserver/qemu) reachable by other local users (piti).
- SEC-30 Review artefact: a reviewer agent created `/tmp/.x` on the VM (2497 B file list of `./scripts/*`, no secrets, 0664) — violation of the read-only rule. Safe to `rm /tmp/.x` with owner OK.

## Checked and fine

- Live path SQL all `?`-parameterised (only f-string: table name in `backup.py:33`, constant).
- subprocess list-form, no `shell=True`/`os.system`; no `yaml.load`/pickle/eval/exec/marshal.
- `evidence.export_requested` validates `request_id` `^[0-9a-f]{32}$` → no path traversal; atomic `mkstemp`+fsync+rename in 0700 dir.
- Journal/lock/bars/evidence files 0600; sender `Umask 0077`; `c22-private` 0700, env files 0600; backups 0600/0700.
- Order-send gating: `MT5_ENABLE_DEMO_ORDER_SEND=1` + `--execute` + review; `broker.identity()` before every `order_send`; only one enabled sender unit.
- Exception/secret hygiene: `public_reason` allow-list; no secrets in journald, `/var/log`, bash_history, process cmdlines; MT5 `common.ini` has login/server only.
- Outbound HTTP uses default TLS verification with timeouts; Telegram/healthcheck env cleared on live units.
- sshd `PasswordAuthentication no`, `KbdInteractive no`; 0 failed password logins; ufw INPUT DROP, only 22/80/443 open; other listeners localhost.
- No world-writable files under c22-demo or /usr/local/bin; stock SUID set; no user crontabs; unattended-upgrades enabled.
- No legacy FastAPI/uvicorn listener on VM or Mac.

## Not covered

OCI-side controls (security lists, IAM, Run Command, boot-volume backups) — invisible from the guest.
The grokbot host itself. CVE lookups for pinned deps (no external lookups done). Content of MT5 Experts/Scripts dirs.

## Status update 2026-11-17 (owner-approved set A)
All items below were applied with backups and verified. Sender and terminal stayed active with NRestarts 0; no position was affected.

| ID | Status | Evidence |
| --- | --- | --- |
| SEC-30 | **Fixed** | `/tmp/.x` removed |
| SEC-12 | **Fixed** | rpcbind socket/service disabled and inactive; nothing on :111 |
| SEC-13 | **Fixed** | `ssl_protocols TLSv1.2 TLSv1.3`, `server_tokens off`; `nginx -t` OK, reloaded; local https 200, TLS 1.1 refused. Backup `nginx.conf.bak-20261117T123315Z` |
| SEC-11 | **Partly fixed** | Drop-in `/etc/ssh/sshd_config.d/50-c22-hardening.conf`: AllowUsers ubuntu, X11/agent forwarding off, MaxAuthTries 3. A fresh login was verified. AllowTcpForwarding was left on (possible owner or bot tunnels). A future `c22mon` user must be added to AllowUsers |
| SEC-8 | **Fixed** | Script installed root:root 755 at `/usr/local/sbin/mt5_ap_lock.sh` and the unit repointed (daemon-reload, no restart). iptables rules unchanged. The old copy remains in `ops-local/` for reference |
| SEC-9 | **Fixed** | `c22-trade-notify` now uses a no-redirect opener and requires https. A local test showed the original re-sent the auth header on a 302 redirect. Backup `/usr/local/bin/c22-trade-notify.bak-<ts>`; service restarted and resumed from its cursor |
| SEC-15 | **Fixed** | `deploy/ops/pull_vm_backup.sh`: first pull 2026-11-17 `demo-20261116T215011905239Z` 96 MB gz, sha matches the VM manifest; weekly scheduled task Sun 10:00 ICT, keeps 4 |
| SEC-17 | **Fixed in repo** | No hardcoded webhook secret. The bridge now fails closed on an empty or burned secret, and auth uses `hmac.compare_digest`. Tests: `tests/webhook/test_webhook_secret_fail_closed.py` passes, webhook suite 98/98. **Owner still has to rotate** the value in `config/settings.yaml` before the bridge can run |
| SEC-18 / SEC-19 | **Fixed** | `config/settings.yaml` set to 0600; secret patterns added to `.gitignore` |
| SEC-3 | **Partly fixed** | `~/ssh-keys` set to 0700. The owner still has to add a passphrase (`ssh-keygen -p`) |
| SEC-5 / SEC-14 | **Snapshot taken** | `deploy/vm-snapshot/2026-11-17/` holds the exact release (88/88 hashes OK), VM tooling and systemd units. Not committed yet |

Still open: SEC-1/I8 (grokbot plan: P1 applied 2026-11-17, P0/P2/P3 pending owner), SEC-2, SEC-4, SEC-6, SEC-7, SEC-10, SEC-16, SEC-20–29.
