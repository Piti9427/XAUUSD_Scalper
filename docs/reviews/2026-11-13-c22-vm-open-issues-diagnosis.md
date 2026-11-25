# C22 Selected26b8 VM — วิเคราะห์ issue ที่ยังเปิด (2026-11-13)

ที่มา: `C22-VM-ISSUES-2026-11-13.md` (I1, I2, I4–I8). วิธี: read-only diagnosis 7 agent + skeptic อิสระ 7 agent
(re-run loop, พยายาม refute). ไม่แตะ live sqlite (query จาก backup `demo-20261112T215003049151Z` copy บน Mac),
ไม่เขียนอะไรบน VM, ไม่ส่ง order/notification. Code อ้างอิง = release ที่รันจริง `selected-23ab6655adee8443`.
Raw output: workflow `wf_9c47760b-0f2` (scratch, ไม่ commit).

## สรุปลำดับความสำคัญ (ใหม่)

| ลำดับ | # | เดิม | ประเมินใหม่ | เหตุ |
|---|---|---|---|---|
| 1 | I1+I5 | ต่ำ / ต่ำ–กลาง | กลาง (ไม่ใช่ emergency) | I1 เขียน audit row ทุก cycle ≈ 1/3 ของ DB growth; weekend cycle เร็ว → model 300–640 MB/day. ไม่มี cliff ก่อนจันทร์ (disk ว่าง 61G, lock ≈2 s/60 s); ขีดจำกัดจริง = disk ≈3 สัปดาห์ (model). Rename ถูกสุด/คุ้มสุด ทำก่อน weekend ได้ประโยชน์เต็ม แต่ไม่บังคับ |
| 2 | I4 | กลาง | กลาง | หมด 2026-11-19 08:14:35 UTC; **ตัวเตือน 18 พ.ย. 09:00 ICT หาไม่เจอทุกที่** |
| 3 | I2 | กลาง | ต่ำ (trading) / กลาง (monitoring) | ไม่ใช่ 6 รายการค้าง — delivery ปิดโดยตั้งใจ, CRITICAL ไม่ถูก relay |
| 4 | I8 | ต่ำ | ต่ำ + **security note** | journal สร้างจาก external host key `grokbot-vm-oracle` ที่อ่าน LIVE DB |
| 5 | I7 | ต่ำ | ต่ำ | 6 ตัว = artefact ของ tree ไม่ครบ; แต่ 23ab เพิ่ม red 2 ตัว + boundary logic ไม่มี test |
| 6 | I6 | ต่ำ | ต่ำ, **อย่า kill** | process เหล่านี้คือ services ตัวจริงของ prefix live |

## I1 — `evidence_packet_context_mismatch`

- **Root cause (high, skeptic ยืนยัน):** `state/forward-evidence/request.json` = request `a09633a8…` (2026-10-29 12:47Z).
  Packet `broker-a09633a8….json` มีอยู่แล้ว capture ใต้ release `b445d0b3`/config `b9c771bf`.
  `scripts/c22_selected/evidence.py:127-139` เข้า idempotent branch → เทียบ `release_hash`/`config_hash`
  (running `23ab6655`/`df6a716a`) ไม่ตรง → raise ทุก cycle.
- Trigger = release เปลี่ยนตอนมี request ค้าง (fault แรก 2026-11-10 05:15:21Z = deploy 8de9). ไม่ใช่อายุไฟล์.
  Request ค้างเพราะ owner-export `d194364d` (10-31) **restore prior bytes** แทน retire (`PRIOR_BYTES_RESTORED`).
- Rollback 8de9 ก็ยัง mismatch.
- **แก้ issue เดิม:** ไม่ใช่แค่ log noise. `record_operational_failure` (`demo_runtime/runner.py:108-126`)
  INSERT audit ไม่ dedupe → 63,038 rows / 85.8 MB (11-10→11-12), ≈24k rows ≈33 MB payload/วัน, 1:1 กับ CYCLE.
- Trading impact: ไม่มี — export รันหลัง `super().cycle()` ใน try/except, ไม่อยู่ใน `known_blockers`, notifier/watchdog ไม่อ่าน.
  แต่ heartbeat มี `requires_operator=true` FAULT ตลอด → กลบ FAULT จริงตัวอื่น.
- **Latent link I4:** `trial_costs._build_trial_policy` (`trial_costs.py:52-57`) ต้องการ broker packet อายุ ≤5 นาที.
  Renewal รอบ 11-19 ต้องโพสต์ request ใหม่อยู่แล้ว (capture ได้เฉพาะตอน flat).
- **Fix:**
  1. ทันที (owner approval, VM write): `mv request.json request.json.retired-20261113` ใน dir เดิม; เก็บ broker-*/receipt/owner-export ไว้ครบ.
     Atomic, ไม่ต้อง restart; race แย่สุด = FAULT 1 cycle. ตรวจว่าไม่มี owner-export lock ค้าง.
     ทางเลือกตาม design: โพสต์ request ใหม่ (ID ใหม่) ตอน flat → ได้ packet สำหรับ renewal ด้วย, แล้ว retire หลัง capture.
  2. Runbook: เพิ่มขั้น retire pending request ก่อนสลับ release; แก้ owner-export script ให้ retire ไม่ restore.
  3. Code (release ใหม่ + review): dedupe `record_operational_failure` per (stage, code, incident) audit เฉพาะ raise/clear/re-raise + heartbeat รายชั่วโมงพร้อม count.
     ห้าม dedupe แบบรายวันเฉย ๆ — OPERATIONAL_FAILURE เป็น audit เดียวของ fault นี้ (CYCLE ไม่มี operational_errors).

### I1 — Applied (owner approved 2026-11-13)

- 06:03:30Z `mv -n request.json request.json.retired-20261113` ใน `state/forward-evidence/` (sha256 `22658e6b…` เท่าเดิม).
  Precondition: ไม่มี owner-export process, lock ไม่ถูกถือ, sender WAIT. broker-*/receipt/owner-export เก็บครบ.
- Verify: ก่อน 06:01:00–06:03:25 = 34 fault lines; หลัง 06:03:35–06:06:06 = 37 cycle lines, **0 fault**, 0 export_failed/Traceback,
  heartbeat `status=WAIT`, `broker_evidence=None`, `operational_errors=None`, `known_blockers=[]`, NRestarts=0. ไม่ restart.
- ยังค้าง: runbook step retire-on-deploy, owner-export retire-not-restore, dedupe `record_operational_failure` (release ใหม่).
  Renewal 11-19 ต้องโพสต์ request ใหม่ตอน flat เพื่อ fresh packet — และ retire หลัง capture.

## I5 — DB โต

- Live: 1,763,749,888 B @ 2026-11-13 05:51Z. Disk ใช้ 36G/96G.
- **Root cause:** `demo_runtime/runner.py:249` เขียน CYCLE (≈2.0–2.8 KB, ทุก row distinct) ทุก cycle; + I1 OPERATIONAL_FAILURE;
  append-only trigger `journal.py:59-60`; ไม่มี prune ใด ๆ. Row > ครึ่ง page 4 KB → file growth ≈1.25–1.48× payload.
  CYCLE = 84% rows / 88% bytes.
- Rate: weekday ≈95–145 MB/day (วัดจาก backup-to-backup). Weekend ก่อน I1 (10-31/11-01) วัดได้ 303–327 MB/day;
  model กับ I1 ≈640 MB/day (upper bound ≈708). **ยังไม่เคยสังเกต weekend จริงบน 23ab+I1** — เป็น model.
- **แก้ issue เดิม:** "1.22 GB (10 พ.ย.)" ผิด — snapshot 11-07→11-10 คงที่ 1,359,953,920 B (sender crash loop). ticket 14 ประเมิน 85 MB/day ต่ำไป.
  Watchdog WARN 2.2 GB และ I1 dedupe (ticket 14/15) **ยังไม่ deploy**.
- Runway: disk ใช้ ≈10× ขนาด journal ตอน backup (live + 7 copies + new + restore temp). Mixed rate ≈278 MB/day → ล้มที่ ≈8 GB ≈ ต้นธ.ค. (≈3 สัปดาห์), ไม่ใช่ 44 วัน.
  Disk เต็ม → commit ล้ม → sender หยุด รวม protection reconciliation.
- WAL: คง DELETE mode. Backup lock ≈2 s vs busy_timeout 60 s (D3 ไม่ใกล้กลับมา). `journal.py:48` อ้าง `wal_migrate.py` ที่ไม่มีอยู่จริง.
- Threshold 2.2/2.5 GB เป็นแค่ trigger ที่วางแผนไว้ (ไม่ deploy) — ข้ามไปก็ไม่มีอะไรเกิด.
- **Fix ตามลำดับ:** (A) แก้ I1 (ลด ≈1/3 weekday, ≈ครึ่ง weekend) — ควรทำก่อน weekend ถ้า owner พร้อม, ไม่ต้องรีบภายใต้แรงกดดัน;
  (B) watchdog size + rate (MB/h) alarm ใช้ `stat` เท่านั้น; (C) CYCLE change-only/slim (audit consumers ก่อน:
  `evidence.py:13`, `c22_selected_readiness.py:35`, `ops/c22_forward_feed.py`, `ops/c22_forward_seal.py`);
  (D) rotation = epoch rollover (freeze เก่า read-only + manifest, journal ใหม่ carry kv/events/UNKNOWN) ห้าม DELETE —
  เป็น contract change ต้อง rehearsal บน backup copy + owner approval + flat window.

## I4 — Review ต้องต่อมือทุก 7 วัน

- **สิ่งที่หมดอายุจริง = cost policy** (`demo_runtime/costs.py:133-136`, reviewed_utc + 168h) ไม่ใช่ review (ไม่มี expiry field).
  Review pin policy hash + release/config/fingerprint/snapshot/contract/magic (`c22_selected/execution.py:100-145`); acceptance ต้องภายใน 5 นาทีของ captured/approved (`:156-160`).
- หมด 2026-11-19 08:14:35 UTC (15:14 ICT, พฤหัส, ช่วงตลาดเปิด).
- หมดแล้ว: flat → `EXECUTION_REVIEW_STARTUP_BLOCKED` ไม่ crash (D2 จริงใน 23ab; **repo local ยัง pre-patch**). มีไม้ → reconcile/protection ต่อ.
  c22-trade-notify ควรยิง `bot_blocked_long` ≈10 นาทีหลังหมด (predicted จาก code, ยังไม่เคยเห็นจริง).
- **ตัวเตือน "18 พ.ย. 09:00 ICT" ไม่พบ** — ไม่มีใน VM timers/crontab, LaunchAgents, Claude scheduled-tasks. Watchdog คำนวณ DUE_72H/24H/6H แต่รันไม่มี `--notify`.
- Renewal ต้อง: flat, no UNKNOWN, exclusive probe (sender หยุด), owner approval ด้วยคำของ owner, accept ภายใน 5 นาที, swap policy→review แบบ atomic.
- Auto-renewal code มีอยู่ (`renewal.py`, `renewal_runtime.py`, `c22_selected/runner.py:182-186`) แต่ปิดโดยตั้งใจ (AGENTS.md "No automatic cost-policy renewal") — **ห้ามเปิด**.
- **Fix:** (A) reminder ฝั่ง Mac/Claude scheduled task trigger ที่ bucket DUE_72H (11-16 08:14Z) / DUE_24H / DUE_6H (dedupe per bucket; ห้ามใช้ exit code ของ probe_i4.py — แดงตลอด);
  (B) เพิ่ม classify `execution_review.policy_due` ใน `/usr/local/bin/c22-trade-notify` (ช่องทางเดียวที่ส่งจริง; ไม่กระทบ release_hash; ต้อง approval + regression จาก recorded journald);
  (C) ทำ ticket 13 decision 2 (ops script เตรียม renewal package, ไม่เขียน approval fields).
  วาง renewal window ตอน flat จ.–พ. 16–18 พ.ย.

## I2 — แจ้งเตือนค้าง

- **Root cause (high):** delivery ปิดโดยตั้งใจ. Unit ตั้ง/unset `DEMO_TELEGRAM_*`/`DEMO_HEALTHCHECK_URL` →
  `demo_runtime/cli.py:131-135` notify=None → `runner.py:268` ข้าม alerts_v1, `journal.py:158-160` flush return ทันที. ไม่เคยพยายามส่ง (deliveries ว่าง, 0 failure audit).
- **แก้ issue เดิม:** ไม่ใช่ 6 แต่ 26 rows (backup) / ≥27 live, sent=0 ทั้งหมด ทุก release. ไม่มี "สาเหตุรายตัว".
  มี outbox ที่ 2 ใน watchdog DB: 175 pending. CRITICAL มี 4 (ไม่ใช่ 3): 11-01 = algo_permissions_required (pos unreadable), 11-02 = foreign_exposure,
  10-29 / 11-11 = quote_stale ช่วง daily break ขณะถือไม้ (protection *unverified* จริง ไม่ใช่ false positive แท้).
- Gate: code gate `pending_outbox` ใน `c22h4_readiness`/`c22_selected_readiness` อ่าน **shadow** journal — ไม่ถูก block. มีแค่ prose runbook "empty outbox" (`docs/ops/c22-selected-demo.md:267,401,545`) ที่ขัดกับ delivery-off.
- **Monitoring gap:** c22-trade-notify relay แค่ OPEN/CLOSE/FOREIGN/bot_blocked_long; CRITICAL/BE_MOVED ไม่ถูกส่ง; quote_stale mute 21:45–23:15 UTC ครอบ break ฤดูหนาว (22:00) แต่ไม่ครอบฤดูร้อน (21:00) → coverage ขึ้นกับ DST.
- **Fix (ทั้งหมดต้อง approval):** (1) trade-notify rising-edge PROBLEM สำหรับ `critical=true` (dedupe ช่วง break ≈60 นาที; อย่า suppress quote_stale);
  (2) แก้ runbook gate เป็น "ไม่มี CRITICAL ที่ยังไม่ review หลัง watermark (id+hash)" ระบุ execution journal ชัด;
  (3) **ห้ามเปิด Telegram env กลับเฉย ๆ** — replay CRITICAL เก่า + ≥22 trade rows + 6,910 BLOCKER + query `NOT IN` บน ≈587k rows ทุก cycle.

## I6 — Wine process ค้าง

- **แก้ issue เดิม:** ไม่ใช่ขยะจาก test. คือ `services.exe`/`winedevice.exe`/`plugplay.exe`/`svchost.exe` **ตัวเดียวของ prefix live**
  ต่อ wineserver 522432 ที่ terminal+sender ใช้อยู่. อยู่ใน `session-4344.scope` (abandoned) เพราะ 2026-11-10 05:18:36 renewal probe
  (`state/staging-deploy-20261110/pkg/renewal-v2/probeA.py`, `MT5_ENABLE_DEMO_ORDER_SEND=0`, ผ่าน `go-renewal.sh:19` `setsid nohup`) spawn ขึ้นใน SSH scope.
- Wine system services เกิดใน cgroup ของ client แรก (python.exe+MetaTrader5) ไม่ใช่ unit ที่ถือ wineserver. Inference: ก่อน 11-10 อยู่ใน execution cgroup และถูก kill/respawn ≈13,800 ครั้งระหว่าง crash loop.
- Cost ≈65 MB PSS, ≈1% core. **ทางเลือกที่ดีที่สุดตอนนี้ = ไม่ทำอะไร.**
- ห้ามเด็ดขาด: `wineserver -k`, `pkill -f wine`, `killall qemu-x86_64*`, `loginctl terminate-user`, kill 522432/522399.
- ถ้าจะเก็บ (approval, flat, ตลาดปิด, นอก 23:50–00:10 UTC): stop execution → `systemctl stop session-4344.scope` → start execution (services respawn ใน execution cgroup = สภาพก่อน 11-10). ไม่ต้อง restart terminal.
  Acceptance ≠ `check_i6.sh` GREEN.
- Prevention: ให้ probe ใน `go-renewal.sh` รันผ่าน `systemd-run --scope/--wait` (recurrence vector จริง).

## I7 — 6 failing tests

- **Root cause:** artefact ของ partial build tree (`runs/c22-batch-a-2026-11-11/tree`) ขาด `smc_main.py`, `.github/workflows/ci.yml`, `tradingview/*.pine`.
  Full repo: application 82/82 OK. (2 FAIL + 4 ERROR, 2 เป็น setUpClass.) ปิดไว้แล้วใน ticket 16.
- **ใหม่:** 23ab เพิ่ม red 2 ตัวใน demo suite:
  (a) registry contract — 15 `held_boundary_*` literals ใน broker.py ไม่อยู่ใน RESUME (แปลงเป็น `day_start_floating_unknown` เสมอ);
  (b) `test_c22h4_trade_log` stub Journal ไม่มี `audit()`.
- **Gap จริง:** held-boundary reconstruction ตั้ง live daily-loss baseline แล้ว (2026-11-12 day_start=369.35) แต่ **ไม่มี test เลย**;
  23ab deploy ไม่มี test log; `boundary.py`/`broker.py`/`lifecycle.py` ของ 23ab อยู่บน VM เท่านั้น — merge เข้า repo ต้อง 3-way (lifecycle.py local ต่างทั้ง 8de9 และ 23ab).
  Fix (a)+(b) ทดสอบแค่ใน scratch copy (demo 574 OK); (b) ผ่านทาง early exit (`held_boundary_currency`) → midnight-hold path ยังไม่ถูก test จริง ต้องเพิ่ม unit test ของ `_held_boundary_value`.
  Latent: แปลงแค่ ValueError; TypeError/KeyError/sqlite error ใน except handler (`broker.py:293-295`) จะ propagate.

## I8 — Trade journal ไม่ถูก track

- `logs/` ถูก gitignore (`.gitignore:36`) — รวมถึงตัว issue doc เอง.
- **แก้:** journal ไม่ได้สร้างบน Mac. Extraction 2026-11-13 01:22Z login ด้วย key comment `grokbot-vm-oracle`
  (external agent host, `/workspace/c22-trade-journal`); Mac เป็นสำเนา copy มือ. `_raw/extract.json` น่าจะอยู่ที่ host นั้น (ไม่ได้ตรวจ).
- **Hazard:** `extract_remote.py` อ่าน **LIVE** sqlite (rollback-journal mode → SHARED lock block commit ได้ถึง 60 s). ไม่เห็นความเสียหาย 01:15–01:45Z แต่ซ้ำทุกครั้งที่ rerun.
- Access note: `~ubuntu/.ssh/authorized_keys` มี 2 key: `ssh-key-2026-06-16` (Mac) + `grokbot-vm-oracle`.
  น่าจะเป็น "กล่องของผู้ช่วย" ตามกฎพื้นฐานใน issue doc (8 source IP สอดคล้อง cloud egress). sshd Accepted publickey ตั้งแต่ 11-11 = 1,029 (skeptic: 842 จาก grokbot).
  ขอ owner ยืนยันว่าเป็นกล่องนั้น — hazard จริงคือ extractor ของมันอ่าน LIVE DB ทุกครั้งที่ rerun, ไม่ใช่ intrusion.
- Durability: backups 7 ชุดอยู่ `/dev/sda1` เดียวกับ state, ไม่มี offsite (OCI boot-volume backup มองไม่เห็นจากใน guest).
  ห้ามเติม `--private-bucket` เฉย ๆ — ไม่มี `oci` CLI → backup unit fail ทุกรอบ. ทางเลือกปลอดภัย: Mac scp pull snapshot `restore_verified` + เช็ค sha256 กับ manifest.
- **Fix:** ย้าย code ไป `scripts/ops/c22_trade_journal/` (อ่าน backup snapshot ไม่ใช่ live DB, key จาก env), output ไป `runs/c22-trade-journal/<stamp>/`, summary redacted ใน `docs/reviews/`. Reconcile กับสำเนาบน external host ก่อน.

## ข้อค้นพบข้างเคียง (ไม่อยู่ในรายการเดิม)

1. Watchdog unit รันจาก release `selected-1c0453dcf92db05d`; backup unit รันจาก `8de9` (backup.py byte-identical ตอนนี้); `current` symlink → `d091bc6b810e792c` (data dir). "release ไหน authoritative" ต่างกันต่อ unit.
2. Watchdog เปิด LIVE journal (`mode=ro`, BEGIN) ทุก 60 s — lock class เดียวกับ D3.
3. Drop-in `20-timeout.conf` เขียนว่า "PROPOSED - NOT APPLIED" แต่ active (TimeoutStartUSec=5min).
4. `docs/ops/c22-selected-demo.md:236-237` ยังบอก backup ทุก 5 นาที (จริง: daily 21:50 UTC).
6. **ยังไม่ verify — ควรตรวจต่อ:** I7 agent รายงานว่า 23ab ไม่มี swap_band 5% (owner decision 2026-11-12, CORE_STRATEGY 6.67), `JOURNAL_BUSY_TIMEOUT_S`, startup-review INVALID variant ที่อยู่ใน local working tree → ถ้าจริง live sender ยัง block เมื่อ swap drift. ขัดกับ D4 ใน issue doc (tolerance adverse10/favourable25) — ต้องเทียบ code 23ab กับ D4 ก่อนสรุป.
7. I2 fix ที่ agent เสนอให้ถือ owned position ใต้ BLOCKED quote_stale ว่าไม่ uncertain — **skeptic ค้าน** (ลด safety alarm; runner ไม่ re-read SL/TP ตอน BLOCKED). ทำได้เฉพาะ downgrade เมื่อ positions read ใน cycle เดียวกันยืนยัน SL/TP.
5. Sender crash loop 11-05→11-10 (13,804 restarts, ValueError ใน `reviewed_runner`) — cross-ref live availability gap.

## ต้องตัดสินใจ (owner)

1. **I1 rename `request.json`** (แนะนำก่อน weekend) หรือโพสต์ request ใหม่ตอน flat เพื่อใช้ใน renewal — อยากได้ fresh capture ไหม?
2. ตั้ง reminder I4 (DUE_72H 11-16 08:14Z) + วาง flat renewal window 16–18 พ.ย.; ยืนยันว่ามี reminder ในมือถือ/ปฏิทินไหม; batch-B จะ deploy ก่อน 19 พ.ย. ไหม (ถ้าใช่ renew ผูก release นั้นทีเดียว).
3. ยืนยัน `grokbot-vm-oracle` = กล่องผู้ช่วย, และให้ extractor เปลี่ยนไปอ่าน backup snapshot แทน live DB.
3b. External delivery OFF ถาวรไหม (T10)? → ถ้าใช่ redefine runbook gate "empty outbox".
3c. Offsite backup: OCI bucket หรือ Mac pull (Time Machine ต้องซ่อมก่อน)? TRADE_JOURNAL (มีเลขบัญชี) ห้ามขึ้น GitHub?
3d. ใคร merge 23ab `boundary.py`/`broker.py`/`lifecycle.py` เข้า repo (3-way)?
4. I2/I4 trade-notify classify เพิ่ม (CRITICAL, policy_due) — VM change.
5. I6: ไม่ทำอะไร (แนะนำ) หรือ cleanup ตาม procedure ข้างบน.
