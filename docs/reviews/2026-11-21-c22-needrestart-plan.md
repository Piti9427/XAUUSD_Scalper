# C22 VM: กันไม่ให้ needrestart restart บอทเอง, 2026-11-21

สถานะ: **ติดตั้งแล้ว 2026-11-22 00:35 UTC** (owner อนุมัติ "อนุมัติติดตั้ง") ผลอยู่ในข้อ 9

## 1. ปัญหา (ยืนยันจาก log แล้ว)

- 2026-11-14 (เสาร์) 06:30:36 UTC: `apt-daily-upgrade` (unattended-upgrades) อัปเกรด `libc6` จาก 2.39-0ubuntu8.9 เป็น 8.12 (`/var/log/dpkg.log`)
- จากนั้น apt hook `/etc/apt/apt.conf.d/99needrestart` เรียก `apt-pinvoke -m u` ซึ่งทำงานใน Ubuntu mode แบบ `restart = 'a'` (อัตโนมัติ)
- 06:30:49–50: systemd สั่ง stop/start `c22-selected-execution`, `c22-selected-terminal`, `c22-trade-notify` และ nginx (journal ของ PID 1)
- `apt-daily-upgrade.timer` ตั้งไว้ `OnCalendar=*-*-* 6:00` + `RandomizedDelaySec=60m` คือรันทุกวัน 06:00–07:00 UTC (13:00–14:00 ICT) ซึ่งในวันธรรมดาตลาดเปิดอยู่
- ผลคือถ้ามี security update ของ library ที่บอทใช้ (libc, python3, openssl ฯลฯ) ระบบจะ restart บอทและ terminal เองได้ แม้ขณะมีไม้เปิด ซึ่งขัดกับกฎ "ห้ามเปลี่ยนอะไรตอนมีไม้เปิด"

## 2. ทางเลือก

| ทาง | ทำอะไร | ข้อดี | ข้อเสีย | ตัดสิน |
|---|---|---|---|---|
| **A** | เพิ่ม drop-in `override_rc` ยกเว้นแค่ execution กับ terminal | เล็กที่สุด; security patch ยังลงอัตโนมัติ; service อื่น (ssh, nginx, notify) ยัง restart อัตโนมัติเหมือนเดิม | บอทจะรันด้วย library เก่าจนกว่าจะ restart ตามแผน | **แนะนำ** |
| B | ตั้ง `$nrconf{restart} = 'l'` (แจ้งรายการอย่างเดียว) | ไม่มีอะไร restart เองเลย | ปิด auto-restart ของทุก service รวม ssh/nginx; การตั้ง `restart` ยังทำให้หลุดจาก Ubuntu mode ด้วย (`/usr/sbin/needrestart` บรรทัด 264–266) | ไม่เลือก |
| C | ย้าย `apt-daily-upgrade.timer` ไปวันเสาร์ | patch ทุกอย่างลงตอนตลาดปิด | security patch ช้าสูงสุด 7 วัน; ยัง restart บอทเองอยู่ดี | ไม่เลือก |
| D | ปิด unattended-upgrades | | เสีย security patch อัตโนมัติ | ไม่เลือก |

## 3. สิ่งที่จะเปลี่ยน (ทาง A)

เพิ่มไฟล์ใหม่ 1 ไฟล์: `/etc/needrestart/conf.d/50-c22-no-auto-restart.conf` (root:root 0644)
ต้นฉบับอยู่ที่ `runs/c22-needrestart-2026-11-21/50-c22-no-auto-restart.conf`, sha256 `e66ae17581d2cda95458fdb058aa42bfa059986158208635407a563fc45c43c6`

```perl
# C22 Selected26b8: do not let unattended-upgrades/needrestart restart the
# trading bot or its MT5 terminal (they may hold an open position).
# Restart them only in an owner-approved, flat, market-closed window.
# Plan: docs/reviews/2026-11-21-c22-needrestart-plan.md
# Rollback: delete this file (needrestart reads config on every run).
$nrconf{override_rc}->{qr(^c22-selected-(execution|terminal)\.service$)} = 0;
```

- ไม่แก้ `needrestart.conf` เดิม (sha256 `baacdd68…f7ee`) ไม่แตะ timer, unattended-upgrades หรือ unit ของบอท และไม่ restart service ใด ๆ
- `needrestart.conf` บรรทัด 229–230 โหลด `conf.d/*.conf` อยู่แล้ว
- กลไกเดียวกันนี้ใช้กับ `apt-daily-upgrade`, `systemd-logind` และ `unattended-upgrades` อยู่แล้ว log เดือน มิ.ย. แสดงว่า 3 ตัวนี้ขึ้นเป็น "Service restarts being deferred" จริง
- c22-trade-notify, backup และ watchdog ยังให้ restart อัตโนมัติได้ เพราะไม่กระทบการเทรด ส่วน `mt5-ap-lock` เป็น oneshot ที่ไม่มี process ค้าง needrestart จึงไม่แตะอยู่แล้ว

## 4. ทดสอบแล้ว (บน Mac ด้วย config จริงที่ copy มาจาก VM)

โหลด `needrestart.conf` ของ VM พร้อม drop-in แล้วจำลอง loop `override_rc` แบบเดียวกับ `/usr/sbin/needrestart` บรรทัด 1092–1096

| unit | ผล |
|---|---|
| c22-selected-execution.service | DEFERRED |
| c22-selected-terminal.service | DEFERRED |
| c22-trade-notify / c22-selected-backup / mt5-ap-lock / nginx / ssh / pm2-piti / systemd-networkd | auto-restart (เหมือนเดิม) |
| apt-daily-upgrade.service | DEFERRED (เหมือนเดิม) |
| `$nrconf{restart}` | ยังเป็น undef จึงคง Ubuntu mode ไว้ |

## 5. ขั้นตอนลงมือ (ทำได้ทุกเวลา เพราะไม่ restart อะไร; ต้องเสร็จก่อน จันทร์ 23 พ.ย. 06:00 UTC / 13:00 ICT)

```bash
# 1) เขียนไฟล์จากต้นฉบับบน Mac แล้วตรวจ hash
scp 50-c22-no-auto-restart.conf ubuntu@VM:~/50-c22-no-auto-restart.conf   # หรือ heredoc ผ่าน ssh
sudo install -o root -g root -m 0644 ~/50-c22-no-auto-restart.conf /etc/needrestart/conf.d/50-c22-no-auto-restart.conf
rm ~/50-c22-no-auto-restart.conf
sha256sum /etc/needrestart/conf.d/50-c22-no-auto-restart.conf   # ต้องได้ e66ae175…c6

# 2) ตรวจว่า needrestart ตัวจริงโหลด config ได้ (โหมด list-only, ไม่ restart อะไร)
sudo needrestart -b -r l; echo "exit $?"        # ต้อง exit 0 และไม่มี error ของ config

# 3) ตรวจ matching ด้วย config จริงบน VM (อ่านอย่างเดียว)
sudo perl -e 'our %nrconf; do "/etc/needrestart/needrestart.conf"; die $@ if $@;
  for my $u (qw(c22-selected-execution.service c22-selected-terminal.service c22-trade-notify.service ssh.service)) {
    my $r=1; for my $re (keys %{$nrconf{override_rc}}) { next unless $u =~ /$re/; $r=$nrconf{override_rc}{$re}; last }
    print "$u ", ($r ? "auto-restart" : "DEFERRED"), "\n" }'

# 4) ยืนยันว่าบอทไม่ถูกแตะ
systemctl show c22-selected-execution c22-selected-terminal -p ActiveEnterTimestamp,NRestarts
```

เกณฑ์ผ่าน:
- hash ตรง
- `needrestart -b -r l` exit 0
- execution/terminal ขึ้น DEFERRED และ ssh/notify ขึ้น auto-restart
- `ActiveEnterTimestamp` ของบอทยังเป็น 2026-11-21 16:00:23 UTC

## 6. หลังจากนี้ (ผลข้างเคียงที่ต้องจัดการ)

- เมื่อมี library update บอทจะรันต่อด้วย library เก่า และจะเห็นในบรรทัด "Service restarts being deferred" ของ `/var/log/unattended-upgrades/unattended-upgrades-dpkg.log`
- เพิ่มรายการตรวจสุดสัปดาห์ (read-only): `sudo needrestart -b -r l | grep NEEDRESTART-SVC` ถ้ามี c22 ขึ้นมา ให้นัด restart ตามแผน
- restart ตามแผน: ทำวันเสาร์หรืออาทิตย์ ช่วงตลาดปิด ตอนไม่มีไม้เปิด หลีกเลี่ยงช่วงห้ามเดียวกับแผน reboot ต้องขออนุมัติ แล้วสั่ง `sudo systemctl restart c22-selected-terminal c22-selected-execution` ตามด้วย post-check ชุดเดียวกับ reboot (`runs/c22-reboot-2026-11-21/check.sh`)
- kernel update ยังต้อง reboot ตามแผนเหมือนเดิม (auto-reboot ปิดอยู่แล้ว)

## 7. Rollback

```bash
sudo rm /etc/needrestart/conf.d/50-c22-no-auto-restart.conf
```

ไม่ต้อง restart หรือ reload อะไร เพราะ needrestart อ่าน config ใหม่ทุกครั้งที่รัน

## 8. ข้อความอนุมัติ

ตัวอย่าง: "อนุมัติติดตั้ง needrestart drop-in ตามแผน 2026-11-21"
ครอบคลุมขั้นตอนในข้อ 5 เท่านั้น ไม่รวมการ restart บอท

## 9. ผลการติดตั้ง (2026-11-22 00:35 UTC, ตลาดปิดวันอาทิตย์)

หลักฐาน: `runs/c22-needrestart-2026-11-21/install.txt`, `verify.txt`

| เกณฑ์ | ผล |
|---|---|
| ไฟล์เป้าหมายไม่มีอยู่ก่อนติดตั้ง | ผ่าน |
| `root:root 0644`, sha256 `e66ae175…c6` | ผ่าน |
| `needrestart.conf` เดิมไม่ถูกแก้ (`baacdd68…f7ee`) | ผ่าน |
| `needrestart -b -r l` | exit 0, kernel 1016 ตรงกับที่คาด (KSTA 1) |
| matching | execution/terminal = DEFERRED; notify, backup, ssh, nginx = auto-restart; `restart` = undef |
| บอทไม่ถูกแตะ | execution/terminal ActiveEnterTimestamp 2026-11-21 16:00:23 UTC, NRestarts 0, active ทั้งหมด |

ยังไม่ได้พิสูจน์กับ library update จริง จะเห็นผลครั้งแรกเมื่อ unattended-upgrades ลง library ที่บอทใช้ ให้ดูบรรทัด "Service restarts being deferred" ใน log ตามข้อ 6
