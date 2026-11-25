# C22 VM: แผน reboot เพื่อใช้ kernel ใหม่ (SEC-6), 2026-11-21

สถานะ: **แผนเท่านั้น ยังไม่ได้ลงมือ** ต้องให้ owner อนุมัติก่อนทุกขั้นที่เปลี่ยนแปลง VM
ข้อมูลทั้งหมดอ่านจาก VM แบบ read-only เมื่อ 2026-11-21 ราว 15:00–15:50 UTC เวลาในเอกสารเป็น UTC และวงเล็บคือ ICT

## 1. ทำไมต้อง reboot

| รายการ | ค่าปัจจุบัน |
|---|---|
| Kernel ที่รันอยู่ | `7.0.0-1013-oracle` |
| Kernel ที่ติดตั้งแล้ว รอ reboot | `7.0.0-1016-oracle` (ค่า default ใน GRUB) |
| แพ็กเกจที่รอ reboot | `linux-image-7.0.0-1016-oracle`, `linux-base`, `libc6` |
| ค้างมาตั้งแต่ | 2026-11-13 (SEC-6) |
| Uptime | 23 วัน (boot ล่าสุด 2026-10-29 12:39) |
| ผลพลอยได้ | ล้าง qemu/Wine process ที่ค้างจาก probe 17 พ.ย. (I6) ไปด้วย |

## 2. หน้าต่างเวลาที่ทำได้

ทำได้เมื่อ: ตลาดปิด, ไม่มีไม้เปิด, ไม่อยู่ในช่วงห้ามตามตาราง และ owner ว่างพอจะเปิด OCI Console ได้หากเกิดปัญหา

| ช่วง (UTC) | ICT | ใช้ได้ไหม |
|---|---|---|
| เสาร์ 21 พ.ย. 16:00–21:00 | 23:00–04:00 | ได้ |
| เสาร์ 21:50 | 04:50 | **ห้าม** (backup) |
| เสาร์ 23:50 – อาทิตย์ 00:10 | 06:50–07:10 | **ห้าม** (UTC day boundary) |
| อาทิตย์ 22 พ.ย. 02:10 | 09:10 | เลี่ยง (`c22-demo-backup.timer`) |
| อาทิตย์ 06:25 ±สุ่ม | 13:25 | เลี่ยง (`apt-daily-upgrade`, ดูข้อ 7) |
| **อาทิตย์ 00:30–01:50, 02:40–06:00 หรือ 07:30–20:00** | **07:30–08:50, 09:40–13:00 หรือ 14:30–03:00** | **แนะนำ** |
| อาทิตย์ 20:55 เป็นต้นไป | 03:55 วันจันทร์ | **ห้าม** (ใกล้ตลาดเปิด, watchdog guard จบ 23:10) |

ตั้งเส้นตายไว้ที่ **อาทิตย์ 20:00 UTC (03:00 ICT จันทร์)** ถ้าหลัง reboot ยังไม่ผ่าน post-check ภายในเวลานี้ บอทจะยังไม่พร้อมตอนตลาดเปิด แต่บัญชีเป็น demo และไม่มีไม้เปิด ผลเสียจึงมีแค่พลาดสัญญาณ

## 3. ความพร้อมที่ตรวจแล้ว (2026-11-21)

| เรื่อง | ผล |
|---|---|
| ไม้เปิด | `observed_positions 0`, `position_protection flat` |
| Unit ที่จะขึ้นเองหลังบูต | execution, terminal, trade-notify, mt5-ap-lock, watchdog/backup timers, nginx, pm2-piti, ufw, `ssh.socket` เป็น enabled ทั้งหมด (`ssh.service` disabled เป็นเรื่องปกติของ 24.04 เพราะใช้ socket activation) |
| ลำดับการขึ้น | execution `After=` terminal; ap-lock `After=` ufw/netfilter-persistent |
| Restart policy | terminal `Restart=always`; execution `on-failure` + backoff สูงสุด 60 s; ไม่มี start limit (`StartLimitIntervalSec=0`) |
| Release manifests | 6d7b, 9cfc, 8de9 ผ่าน `sha256sum --check` |
| Journal ข้าม boot | persistent (`/var/log/journal`) จึงอ่าน log ของ boot ก่อนหน้าได้ |
| Backup ล่าสุด | `demo-20261120T215016239931Z` ถ่ายหลังตลาดปิดวันศุกร์, `restore_verified: true` |
| Auto-reboot ของ unattended-upgrades | ปิดอยู่ (ค่า default ถูก comment) |
| Kernel เดิมสำรอง | 1013 ยังติดตั้งอยู่ใน GRUB |
| ครั้งก่อน | reboot 2026-10-29 สำเร็จ ระบบกู้คืนเองอัตโนมัติ (`docs/reviews/2026-10-29-c22-attended-reboot-verdict.md`) terminal exit 1 ครั้งแรกแล้วขึ้นเองหลัง 10 s |

**ความเสี่ยงที่รู้อยู่แล้ว:**
- terminal ไม่ได้ `After=mt5-ap-lock` จึงอาจต่อ AP อื่นได้ก่อน lock ทำงาน แต่ rule REJECT/tcp-reset จะตัดและบังคับให้ต่อใหม่ไป AP#1 ต้องเช็กใน post-check
- qemu-user และ Wine บน kernel ใหม่ยังไม่เคยทดสอบ (เป็น patch release ภายใน 7.0 ความเสี่ยงต่ำ แต่มีทางถอยในข้อ 6)

## 4. Pre-check (read-only, ทำก่อน reboot ไม่เกิน 15 นาที)

ทุกข้อต้องผ่าน ถ้าข้อใดไม่ผ่านให้หยุด

```bash
date -u; cat /proc/sys/kernel/random/boot_id; uname -r
systemctl is-active c22-selected-execution c22-selected-terminal c22-trade-notify mt5-ap-lock
systemctl show c22-selected-execution -p NRestarts; systemctl show c22-selected-terminal -p NRestarts
readlink ~/c22-demo/state/c22-selected-execution-review.json ~/c22-demo/state/cost-policy-runtime.json
python3 - <<'PY'
import sqlite3, json, hashlib
c = sqlite3.connect("file:/home/ubuntu/c22-demo/state/c22-selected-execution.sqlite3?mode=ro", uri=True, timeout=10)
r = json.loads(c.execute("select value from kv where key='last_result'").fetchone()[0])
print("status", r.get("status"), r.get("reason"))
def walk(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("observed_positions", "position_protection", "owned_position_protection"): print(p+k, v)
            walk(v, p+k+".")
walk(r)
print("max_audit", c.execute("select max(rowid) from audit_events").fetchone()[0])
for k in ("day", "utc_boundary_mark", "selected_last_loss_ms", "identity", "active", "selected_execution_review_sha256"):
    v = c.execute("select value from kv where key=?", (k,)).fetchone()
    print(k, hashlib.sha256((v[0] if v else "").encode()).hexdigest()[:16])
c.close()
PY
sudo ss -tnp state established '( dport = :443 )' | grep -c 52.221.81.217
df -h / | tail -1
```

เกณฑ์ผ่าน:
- `observed_positions 0` และ `position_protection flat`
- เวลาไม่อยู่ในช่วงห้ามตามข้อ 2
- service ทั้ง 4 ตัว active
- เก็บผลลัพธ์ทั้งหมดไว้ใน `runs/c22-reboot-2026-11-21/pre.txt` บน Mac (ไฟล์นี้มีแค่ hash ไม่มี secret)

**เงื่อนไขฝั่ง owner:** เข้า OCI Console ของ instance นี้ได้ (เมนู Reboot และ Console connection) เพราะเป็นทางกู้เดียวถ้า SSH ไม่กลับมา

## 5. ขั้นตอน reboot (เปลี่ยนแปลง VM ทำครั้งเดียว)

```bash
sudo systemctl reboot
```

- ไม่ upgrade แพ็กเกจอื่นในรอบเดียวกัน (ยังมี upgradable ที่ไม่ใช่ security อีก 71 ตัว แยกไว้ทำทีหลัง)
- ไม่แก้ unit, review, policy หรือ release ใด ๆ
- ไม่ต้องหยุด service ก่อน เพราะ systemd หยุด execution ก่อน terminal ตามลำดับ `After=` อยู่แล้ว โดยใช้ SIGINT และ `TimeoutStopSec=30`
- **ไม่ reboot ซ้ำเองโดยอัตโนมัติ** ถ้าต้อง reboot ครั้งที่สอง (เช่นถอยกลับ kernel) ต้องขออนุมัติใหม่
- **ระหว่าง reboot จะมี webhook แจ้งเตือนเข้ามา** เช่น PROBLEM/RECOVERED (`bot_blocked_long` หรือบอทหยุด) จาก trade-notify ระหว่างและหลังบูต เป็นเรื่องปกติของ maintenance นี้ ไม่ใช่ incident

## 6. Post-check (เริ่มหลัง SSH กลับมา, ดูต่อเนื่องราว 10–15 นาที)

```bash
cat /proc/sys/kernel/random/boot_id; uname -r; ls /var/run/reboot-required 2>&1
systemctl --failed --no-legend
systemctl is-active c22-selected-execution c22-selected-terminal c22-trade-notify mt5-ap-lock mt5-ap-watchdog.timer c22-selected-watchdog.timer c22-selected-backup.timer ufw nginx pm2-piti
systemctl show c22-selected-execution -p NRestarts,ActiveEnterTimestamp; systemctl show c22-selected-terminal -p NRestarts,ActiveEnterTimestamp
sudo iptables -S MT5_AP_LOCK | head -3
sudo ss -tnp state established '( dport = :443 )'
journalctl -u c22-selected-execution -b -o short-iso | grep -iE 'Traceback|source_drift|review_invalid|exited' | tail
journalctl -u c22-selected-execution --since -60s -o cat | tail -1 | grep -oE '"(status|reason|code|execute)": "?[a-zA-Z0-9_]*' | head -8
journalctl -u c22-selected-terminal -b -o short-iso | tail -5
~/c22-demo/ops-local/mt5_ap_watchdog.sh --dry-run
sudo sshd -T | grep -E '^(allowusers|passwordauthentication|maxauthtries) '
sudo ufw status | head -3
pgrep -fa qemu-x86_64 | wc -l
```

รันสคริปต์ DB ในข้อ 4 ซ้ำอีกรอบ แล้วเทียบผลกับ `pre.txt`

| ต้องเห็น | หมายเหตุ |
|---|---|
| boot_id เปลี่ยน, `uname -r` = `7.0.0-1016-oracle`, ไม่มีไฟล์ `reboot-required` | |
| ไม่มี unit failed และ service ทั้งหมด active | terminal อาจ exit 1 หนึ่งครั้งตอนเริ่ม แล้วขึ้นเองหลัง 10 s (เคยเกิด 10-29) ถือว่ายอมรับได้ |
| chain `MT5_AP_LOCK` มีอยู่ และ terminal ต่อ 52.221.81.217:443 เท่านั้น | ถ้าต่อ IP อื่นให้รอ 2 นาทีแล้วเช็กใหม่ ถ้ายังไม่ใช่ AP#1 ให้หยุดและรายงาน ห้ามคลิกเอง |
| execution log ไม่มี Traceback, `source_drift` หรือ `review_invalid` | |
| cycle ล่าสุด: `execute` true, review `VALID`, status BLOCKED `quote_stale` | สถานะนี้คือปกติของวันหยุด รอบแรกอาจขึ้น `armed_trial_new_closed_m15_required` หรือ seed `not_loaded` แล้วรอบถัดไปจะเป็น `restored` |
| readlink ของ review/policy ตรงกับ pre | |
| kv: `identity`, `selected_execution_review_sha256`, `active`, `selected_last_loss_ms` **ต้องตรง** กับ pre; `max_audit` ต้องเพิ่มขึ้น (ไม่ลด) | `day` และ `utc_boundary_mark` **เปลี่ยนได้** (เปลี่ยนทุกวัน) ส่วน `last_bar` เปลี่ยนได้แต่วันหยุดไม่ควรเปลี่ยน เกณฑ์นี้มาจากการเทียบ snapshot 7 ชุด (14–20 พ.ย.): `identity` และ `strategy_snapshot` คงที่ตลอด รวมถึงข้าม restart ตอน deploy 18 พ.ย.; review sha เปลี่ยนแค่ตอน deploy; `active` เปลี่ยนเฉพาะตอนมีไม้เปิด |
| watchdog dry-run ขึ้น "market closed … no click" | |
| sshd/ufw hardening ยังเหมือนเดิม | |
| จำนวน qemu process ลดลง (ตัวค้างจาก probe หายไป) | |

**ตรวจรอบสอง (ตอนตลาดเปิด):** อาทิตย์ 22 พ.ย. ราว 23:10 UTC (06:10 ICT จันทร์ 23 พ.ย.) ต้องเห็น quote_stale หายไป, ยังต่อ AP#1 อยู่, และไม่มี `algo_permissions_required`

## 7. ทางถอย

| อาการ | สิ่งที่ทำ | ใครทำ |
|---|---|---|
| SSH ไม่กลับมาภายใน 10 นาที | owner เปิด OCI Console แล้วดู Console connection / serial log หรือสั่ง Reboot จาก Console | owner |
| บูตได้ แต่ terminal หรือ execution crash วนเพราะ kernel ใหม่ (qemu/Wine) | ขออนุมัติ reboot ครั้งที่ 2 เพื่อกลับไป kernel เดิมครั้งเดียว: `sudo grub-reboot 'gnulinux-advanced-2030c42d-41f8-4b39-9431-34adc8faad8a>gnulinux-7.0.0-1013-oracle-advanced-2030c42d-41f8-4b39-9431-34adc8faad8a' && sudo systemctl reboot` (`grub-reboot` มีผลรอบเดียว default ยังเป็น 1016; ตรวจแล้ว `grub.cfg` รองรับ `next_entry` (6 จุด), `grub-editenv list` อ่านได้ (ว่าง), `/boot/vmlinuz` ชี้ไป 1016) | Claude หลังได้อนุมัติ |
| review/policy invalid | ห้ามแก้ไฟล์ด้วยมือ ให้ fix forward ด้วย go-deploy/renewal ตามปกติ | Claude + owner |
| terminal ไม่ยอมต่อ AP#1 | เก็บหลักฐานแล้วรายงาน ห้าม disable lock และห้ามคลิกเองช่วงตลาดปิด | Claude |
| DB หรือ journal เสีย (ไม่น่าเกิด) | ห้าม restore ทับเอง ให้หยุดแล้วรายงาน ใช้ backup `demo-20261120T215016239931Z` ได้หลังได้อนุมัติแยก | owner ตัดสิน |

## 8. เรื่องที่พบระหว่างเตรียม (ไม่อยู่ในขอบเขต reboot นี้)

- **unattended-upgrades + needrestart restart บอทเองได้ (ยืนยันจาก log แล้ว):** เมื่อ 2026-11-14 (เสาร์) 06:30:36 UTC `apt-daily-upgrade` อัปเกรด `libc6` 2.39-0ubuntu8.9 เป็น 8.12 (`/var/log/dpkg.log`) จากนั้นเวลา 06:30:49–50 systemd สั่ง stop/start `c22-selected-execution`, `c22-selected-terminal`, `c22-trade-notify` และ nginx ทั้งหมด ตอนนั้นเป็นวันเสาร์จึงไม่มีผล แต่ timer นี้รันทุกวันราว 06:xx UTC (13:xx ICT) ซึ่งเป็นช่วงตลาดเปิดในวันธรรมดา ถ้ามี security update ของ library ที่บอทใช้ ระบบจะ restart ทั้ง terminal และบอทเองได้ แม้ขณะมีไม้เปิด ทางแก้ที่เล็กที่สุด (ต้องอนุมัติแยก) คือ drop-in ของ needrestart ให้แค่แจ้งรายการ (`$nrconf{restart} = 'l'`) หรือ blacklist unit `c22-*`/`mt5-*` แล้วให้ security patch ยังลงอัตโนมัติเหมือนเดิม
- handoff ยังเขียนว่าใช้ "Box64" แต่ที่รันจริงคือ `qemu-x86_64-with-trapno` ใน `~/c22-qemu-control/` ควรแก้ handoff

## 9. ข้อความอนุมัติที่ต้องได้จาก owner

ต้องมีทั้งการอนุมัติและช่วงเวลา ตัวอย่าง: "อนุมัติ reboot VM ตามแผน 2026-11-21 ช่วง <เวลา ICT>"
การอนุมัตินี้ครอบคลุม reboot 1 ครั้งตามข้อ 5 กับ post-check เท่านั้น ไม่รวม reboot ครั้งที่ 2, การแก้ needrestart หรือการ upgrade อื่น

## 10. ผลการทำ (2026-11-21)

owner อนุมัติช่วง "คืนนี้ 23:00–04:00 ICT" pre-check ผ่าน (flat, 4 service active) สั่ง `sudo systemctl reboot` ครั้งเดียวเวลา 16:00:02 UTC (23:00 ICT) และ SSH กลับมาตอน 16:00:25 UTC หลักฐานดิบอยู่ที่ `runs/c22-reboot-2026-11-21/{pre,post}.txt`

| รายการ | ผล |
|---|---|
| boot_id | `2b7e2197…` เปลี่ยนเป็น `a596f999…` |
| kernel | `7.0.0-1016-oracle`; ไม่มี `reboot-required` แล้ว |
| service | ทั้งหมด active เวลา 16:00:23 UTC, NRestarts 0 ทั้ง execution และ terminal (รอบนี้ terminal ไม่ exit 1) |
| review/policy | readlink เหมือนเดิม, review `VALID`, `execute` true |
| kv ที่ต้องตรง | identity, review sha, active, last_loss, strategy_snapshot ตรงทั้งหมด (day, utc_boundary_mark, last_bar ก็ไม่เปลี่ยนเช่นกัน) |
| audit | 969381 เพิ่มเป็น 969515 |
| AP | terminal (pid 1333/1390) ต่อ 52.221.81.217:443 เท่านั้น |
| Log | Traceback, source_drift หรือ review_invalid = 0 มีแค่ warning working directory ของ Wine ที่เคยเห็นทุกครั้ง |
| watchdog | "market closed … no click" |
| sshd/ufw | hardening เหมือนเดิม |
| qemu ค้าง (I6) | หายแล้ว process qemu ทั้ง 9 ตัวเป็นของที่เริ่มใหม่หลังบูต |

**ยังเปิดอยู่:** `history_seed_status` ก่อนบูตเป็น `restored` หลังบูตเป็น `not_loaded` ครั้งก่อน (10-29) ค่านี้กลับเป็น `restored` ใน cycle ถัดมา เพราะตอนนั้นมีแท่ง M15 ใหม่ปิด แต่วันหยุดไม่มีแท่งใหม่ จึงคาดว่าจะ restored ที่แท่ง M15 แรกหลังตลาดเปิด (ยังไม่ได้ยืนยัน) ต้องเช็กในรอบตลาดเปิด อาทิตย์ 22 พ.ย. ราว 23:10 UTC (06:10 ICT จันทร์)
