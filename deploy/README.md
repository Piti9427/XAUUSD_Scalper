# Oracle Cloud Free Tier & Docker Deployment Guide (XAUUSD SMC v1)

คู่มือการ Deploy ระบบ **XAUUSD SMC Scalper v1 Copilot** ขึ้นบน Cloud VM (เช่น Oracle Cloud Free Tier) ด้วย Docker และ Headless Wine อย่างมั่นคง ปลอดภัย และป้องกันปัญหา Memory Out-Of-Memory (OOM) 100%

---

## 1. Cloud Server Specification & Architecture

ระบบ XAUUSD SMC Scalper v1 รองรับทั้ง **Ampere A1 (ARM64)** และ **AMD (x86_64)**:

| Parameter | Ampere A1 (ARM64) | AMD E2.1.Micro (x86_64) | คำแนะนำ |
| :--- | :--- | :--- | :--- |
| **Shape** | `VM.Standard.A1.Flex` | `VM.Standard.E2.1.Micro` | ฟรีทั้งคู่ภายใต้ Always Free Tier |
| **CPU / RAM** | สูงสุด 4 OCPU / 24 GB RAM | 1 OCPU / 1 GB RAM | **Ampere A1 แรงกว่ามาก** รองรับงานประมวลผลหนัก |
| **บทบาทหลัก** | **High-Perf Copilot / Analytics** | **Direct MT5 Native Desktop** | ดูรายละเอียดด้านล่าง |
| **Swap Space** | ไม่จำเป็น (RAM 24GB เหลือเฟือ) | **จำเป็นต้องตั้ง 4GB Swap** | ป้องกัน OOM บนเครื่อง AMD 1GB RAM |

### การเลือกใช้งานระหว่าง Ampere A1 (ARM) กับ AMD (x86_64):
1. **เมื่อใช้งานบน Ampere A1 ARM (เครื่องที่คุณมี):**
   - รันระบบ **Telegram Signal Copilot** (คำนวณ SMC Setup, กรองข่าวเศรษฐกิจ, คำนวณ Lot 0.5%, วาดชาร์ตกราฟส่งเข้า Telegram, บันทึก SQLite) ได้อย่างรวดเร็วและทรงพลังที่สุดแบบ Native ARM64
   - หากต้องการส่งคำสั่งเข้า MT5 สามารถใช้ผ่าน MetaApi / Broker REST API หรือเปิดเครื่อง AMD เล็กๆ อีกตัวเป็น Execution Bridge
2. **เมื่อใช้งานบน AMD Micro:**
   - เหมาะสำหรับการรัน Windows MetaTrader 5 Terminal ตรงๆ ผ่าน Wine Headless

---

## 2. Step 1: Configure Swap Space (สำหรับ AMD 1GB RAM)

*หากใช้เครื่อง **Ampere A1 ARM (RAM 24GB)** สามารถข้ามขั้นตอนนี้ไปยัง Step 2 ได้ทันที*  
*แต่หากใช้เครื่อง **AMD Micro (RAM 1GB)** ให้รันสคริปต์นี้เพื่อป้องกัน OOM:*

รันสคริปต์อัตโนมัติ (Idempotent):
```bash
sudo bash deploy/setup_oracle_swap.sh
```

ตรวจสอบผลลัพธ์ด้วยคำสั่ง:
```bash
free -h
```
*คุณควรเห็น `Swap: ~4.0Gi` ปรากฏในตาราง memory*

---

## 3. Step 2: Install Docker & Docker Compose

รันคำสั่งติดตั้ง Docker Engine บน Ubuntu 22.04:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```
*(หากเพิ่มสิทธิ์กลุ่ม docker ให้ทำการ logout และ ssh เข้ามาใหม่ 1 ครั้ง)*

---

## 4. Step 3: Clone Code & Configure Secrets

```bash
# โคลนโปรเจกต์มายัง Server
git clone <YOUR_PRIVATE_REPO_URL> XAUUSD_Scalper
cd XAUUSD_Scalper

# คัดลอก Template สำหรับ Configuration
cp config/settings.yaml.example config/settings.yaml
cp .env.example .env

# แก้ไข Credentials ให้ถูกต้อง
nano config/settings.yaml
nano .env
```

### รายการสำคัญที่ต้องตั้งค่า:
1. `config/settings.yaml`:
   - `mt5.login`, `mt5.password`, `mt5.server` (สำหรับเชื่อมต่อ Broker)
   - `telegram.enabled: true`
   - `telegram.token` และ `telegram.chat_id`
2. `.env`:
   - กำหนด `MT5_PASSWORD`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` หากใช้ Environment variable overrides

---

## 5. Step 4: Build & Launch Container

ใช้ Docker Compose สั่ง Build Image และรันเป็น Background Daemon:

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

---

## 6. Operations & Monitoring

### ดู Live Log แบบ Real-time
```bash
docker logs -f xauusd_smc_copilot
```

### ตรวจสอบสถานะ Container และการใช้ RAM
```bash
docker stats xauusd_smc_copilot
```

### ตรวจสอบ SQLite Trade Audit Trail
```bash
sqlite3 data/smc_trades.db "SELECT id, timestamp, event_type, direction, entry_price, pnl_r, reason FROM trade_lifecycle ORDER BY id DESC LIMIT 10;"
```

### Restart / Stop Container
```bash
# Restart
docker compose -f deploy/docker-compose.yml restart

# Stop
docker compose -f deploy/docker-compose.yml down
```

---

## 7. Troubleshooting & Safety Checklist

1. **Telegram ไม่แจ้งเตือน:**
   - เช็คว่าบอทถูก `/start` ในกลุ่มหรือห้องแชทแล้วหรือยัง
   - ตรวจสอบ `chat_id` ว่าถูกต้อง (ห้องกลุ่มมักขึ้นต้นด้วยเครื่องหมายลบ `-`)
2. **MT5 Connection Failed:**
   - ตรวจสอบชื่อ Server ใน MT5 ให้ตรงกับของ Broker ทุกตัวอักษร (เช่น `ICMarketsSC-Demo`)
   - หากรันบน macOS / Linux โดยไม่มี Wine MT5 Terminal ติดตั้ง ระบบจะเข้าสู่ **Dry-Run Mode** โดยอัตโนมัติ เพื่อความปลอดภัยและไม่ Crash
3. **News Blackout Window:**
   - ระบบจะบล็อกการเปิด Order ใหม่อัตโนมัติในกรอบ 30 นาทีก่อนและหลังข่าวแดง USD (จาก ForexFactory feed)
