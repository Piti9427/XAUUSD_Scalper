# สรุปภาพรวมโครงการ XAUUSD Scalper (Project Overview & Architecture)

> **ปรัชญาสถาปัตยกรรม:** **"Core Engine คงกระพัน — Strategy เป็น Pluggable Adapter"**  
> ระบบนี้แยกส่วน **Core Platform Engine (`scripts/demo_runtime/`)** ซึ่งทำหน้าที่ควบคุมความเสี่ยง, จัดการข้อมูลราคา, การส่งคำสั่ง และการกระทบยอดตั๋ว ออกจาก **Trading Logic/Strategy** อย่างเด็ดขาด ทำให้สามารถวิจัยและเปลี่ยนกลยุทธ์การเข้าออกออร์เดอร์ได้ตลอดเวลาโดยไม่ต้องแก้ระบบพื้นฐาน  
> **เอกสารสถาปัตยกรรมฉบับเต็ม:** [`docs/CORE_ARCHITECTURE.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/CORE_ARCHITECTURE.md)  
> **สถานะปัจจุบัน (24 ตุลาคม 2026):** Phase: Oracle Linux Cloud VM / macOS Demo Shadow & Attended Execution Preparation  
> **การใช้งานเงินจริง (Real-Money):** 🚫 **PROHIBITED (NO-GO)** — ห้ามใช้เทรดบัญชีจริงเด็ดขาด  
> **ชุดการทดสอบครอบคลุม:** **156 Demo Tests** / **1,036 Full Suite Tests** (Unit, Regression & Containment)

---

## 1. วัตถุประสงค์และกรอบการทำงาน (Project Purpose & Scope)

โครงการ **XAUUSD Scalper** พัฒนาขึ้นเพื่อสร้างแพลตฟอร์มการเทรดอัตโนมัติและวิจัยย้อนหลัง (Algorithmic Trading & Research Platform) สำหรับทองคำ (XAUUSD) บนบัญชีขนาดเล็ก (Micro-Capital Base $200) มุ่งเน้น:

1. **สถาปัตยกรรม Deep Modules:** ซ่อนความซับซ้อนของการเชื่อมต่อ Broker MT5 และการจัดการตั๋วไว้หลัง Interface กะทัดรัด
2. **การควบคุมความเสี่ยงระดับสถาบัน (Risk Gates):** คุมเพดานความเสี่ยงต่อไม้ (Per-trade Risk Cap) และเพดานขาดทุนต่อวัน (Daily Loss Circuit Breaker)
3. **การประเมินผลที่สมจริง (Realistic Simulation):** รวมต้นทุนแฝง Spread, Slippage, Commission และบังคับคิดค่า Swap เสมอตาม **Mandatory Swap Policy**

### สเปกบัญชีเป้าหมาย (Reference Target Profile)
- **Symbol:** XAUUSD / `XAUUSDm` (Exness Standard Demo, Contract Size: 100 oz/lot, Min/Step: 0.01 lot)
- **ทุนตั้งต้นอ้างอิง:** $200 USD (Day baseline ล่าสุดใน Demo Journal: $1,812.21 USD)
- **แพลตฟอร์มการเทรด:** MetaTrader 5 (Windows MT5 API ผ่าน Wine บน macOS และ Oracle Linux VM ผ่าน Box64/Wine)
- **สแต็กเทคโนโลยี:** Python 3, SQLite (Journal & Atomic Backup), Systemd Services, Postman Mock Simulations

---

## 2. สถาปัตยกรรมแกนกลาง 5 เสาหลัก (The 5 Core Engine Pillars)

หัวใจของระบบอยู่ในโฟลเดอร์ [`scripts/demo_runtime/`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/) ซึ่งทำงานเป็นอิสระจากตรรกะของกลยุทธ์:

```mermaid
flowchart TD
    subgraph Data Pipeline [1. Market Data Seam]
        MT5[Broker Feed M1] --> M1Validator[market_data.py: Closed M1 Only]
        M1Validator --> M15Assembler[pure_b1.broker_data: ประกอบครบ 15/15 นาที]
    end

    subgraph Pluggable Strategy [2. Strategy Adapter Seam]
        M15Assembler --> StrategyAdapter["Strategy Adapter (C22, Trial30, หรือกลยุทธ์ใหม่)\n- frame(): สัญญาณ BUY/SELL\n- levels(): Entry, SL, TP\n- protects(): กฎ Break-Even"]
    end

    subgraph Core Runtime Engine [3. Core Engine (scripts/demo_runtime/)]
        StrategyAdapter --> Admission[admission.py: Gatekeeper ตรวจงบความเสี่ยง]
        Admission --> Intent[journal.py: บันทึก Intent ลง SQLite ก่อนส่งคำสั่ง]
        Intent --> Dispatch[broker.py: MT5 OrderSend / Demo Identity Guard]
        Dispatch --> Lifecycle[lifecycle.py: Reconcile Fills, Non-widening SL, Safety Close]
    end

    subgraph Durability & Operations [4. Resilience & Outbox]
        Lifecycle --> SQLite[(c22h4-demo.sqlite3)]
        SQLite --> Outbox[delivery.py: Non-blocking Outbox & HTTP Deadlines]
        SQLite --> Backup[backup.py: Atomic SQLite Vacuum & 7 Snapshots]
        SQLite --> Evidence[evidence.py: สถิติ Prospective PnL & Drawdown]
    end
```

1. **Data Integrity Pipeline ([`market_data.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/market_data.py)):** ห้ามใช้ Forming Bar, M15 ต้องประกอบจาก M1 ครบ 15/15 นาทีเท่านั้น
2. **Admission Gatekeeper ([`admission.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py)):** คุม Single-Position, ตรวจสอบเพดานเสี่ยงต่อไม้ (Risk Cap) ร่วมกับค่าคอมมิชชันและสลิปเพจ, คุม Daily Loss Limit, **ถ้าเสี่ยงเกินงบให้ Reject ทันที ห้ามลดขนาดล็อต (Never Clamp Lot)**
3. **Write-Ahead Intent ([`journal.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/journal.py)):** บันทึกเจตนารมณ์ `SENDING` ลง SQLite ก่อนส่งคำสั่งจริง, หาก Timeout จะคงสถานะ `UNKNOWN` รอ Reconcile ป้องกัน Double Send
4. **Lifecycle & Reconciliation ([`lifecycle.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/lifecycle.py)):** ยึดตั๋วด้วย Stable Position ID, ตรวจสอบห้ามขยาย SL ทุก cycle (Non-widening SL), สั่ง Safety Close ทันทีหากตรวจพบออร์เดอร์ผิดสัญญา
5. **Durability & Outbox ([`delivery.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/delivery.py), [`backup.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/backup.py)):** จัดส่งแจ้งเตือนผ่าน Outbox แบบ Asynchronous มี HTTP Deadline ไม่ดึงรอบบอท, สำรองฐานข้อมูล SQLite อัตโนมัติหมุนเวียน 7 Snapshot

---

## 3. ช่องเชื่อมต่อกลยุทธ์ (The Strategy Adapter Seam)

เมื่อต้องการปรับปรุงหรือเปลี่ยนกลยุทธ์ใหม่ กลยุทธ์นั้นจะต้องสร้างเป็น Adapter ที่ส่งมอบ 3 เมธอดหลักตามสัญญา (Contract):

```python
class CustomStrategy:
    magic: int         # หมายเลขประจำกลยุทธ์
    snapshot: str      # รหัส Snapshot ประจำเวอร์ชัน
    risk_cap: float    # เพดานความเสี่ยงต่อไม้ (เช่น 0.10)
    
    def frame(self, m15_bars, h4_bars) -> dict:
        """ตรวจจับสัญญาณจากแท่งปิดสมบูรณ์: คืนค่า 1 (BUY), -1 (SELL), หรือ 0"""
        ...
        
    def levels(self, direction: int, quote: dict, atr: float) -> dict:
        """คำนวณระดับราคา: คืนค่า entry, sl, tp"""
        ...
        
    def protects(self, direction: int) -> bool:
        """กำหนดว่าฝั่งนี้ใช้ Break-Even หรือไม่"""
        ...
```

จากนั้นสามารถนำไปรันบน Core Engine ได้ทันที:
```python
runner = DemoRunner(strategy=CustomStrategy(), journal_path="data/my_bot.sqlite3")
runner.cycle(now=clock_now())
```

---

## 4. กลยุทธ์อ้างอิงปัจจุบันบน Demo (Current Reference Strategy: C22H4)

ปัจจุบันโครงการเลือกใช้กลยุทธ์ **C22 + H4 EMA200** (Snapshot: `RESEARCH-C22-H4EMA200-20261004` / Config: `1af968e9ac6a26ea`) เป็นตัวแทนสำหรับทดสอบบน Exness Demo:

*สัญญาอ้างอิง:* [`CORE_STRATEGY.md` หัวข้อ 6.33](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/CORE_STRATEGY.md#L500-L545) และ [`config/c22h4-demo.json`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/config/c22h4-demo.json)

| พารามิเตอร์ | ฝั่ง BUY | ฝั่ง SELL |
| :--- | :--- | :--- |
| **สัญญาณเข้า (Trigger)** | RSI(14) cross >= 25 จากด้านล่าง + Delta ราคาปิดเป็นบวก | ราคาปิด M15 ทะลุ Low ต่ำสุด 96 แท่งย้อนหลัง (Donchian 96) |
| **ตัวกรองแนวโน้ม M15** | ราคาปิด > EMA 50 และ EMA 50 > EMA 50 (ย้อนหลัง 4 แท่ง) | ราคาปิด < EMA 50 และ EMA 50 < EMA 50 (ย้อนหลัง 4 แท่ง) |
| **ตัวกรองมหภาค H4** | ราคาปิดแท่ง H4 ล่าสุด > EMA 200 | ราคาปิดแท่ง H4 ล่าสุด < EMA 200 |
| **Stop Loss (SL)** | 1.5 ATR | 2.5 ATR |
| **Take Profit (TP)** | 2R (คำนวณจาก 2 เท่าของระยะ Entry-to-SL ปัดเศษ) | 3.0 ATR |
| **Break-Even (BE)** | ปิดการป้องกัน (Protection Off) | BE 1R (เมื่อกำไรแตะ >= 1R เลื่อน SL ไปจุดคุ้มทุน) |
| **ขนาดล็อต** | **0.01 lot คงที่** | **0.01 lot คงที่** |
| **เพดานเสี่ยงต่อไม้** | <= 10% ของ Equity | <= 10% ของ Equity |
| **เพดานเสี่ยงต่อวัน** | <= 10% ของ Day-Start Equity (UTC) | <= 10% ของ Day-Start Equity (UTC) |
| **ลิมิตการแพ้ต่อวัน** | อนุญาตแพ้ได้สูงสุด 1 ครั้งต่อวัน UTC | อนุญาตแพ้ได้สูงสุด 1 ครั้งต่อวัน UTC |

*กลยุทธ์ Rollback สำรอง:* **Trial30** (SELL-only Donchian 48 + TP 3 ATR + BE 1R + Daily 20%) ถูกเก็บไว้ใน [`scripts/trial30/`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/trial30/) เสมอ

---

## 5. กฎเหล็กประจำ Core System ที่ไม่มีวันเปลี่ยนแปลง (Non-Negotiable Invariants)

ไม่ว่าจะปรับแต่งกลยุทธ์ไปในทิศทางใด กฎเหล่านี้เป็น Invariants สากลของทั้งระบบ:

1. **Zero Real Money:** ระบบนี้ไม่รองรับการเทรดเงินจริง และมีตัวบล็อกบัญชีจริงในระดับโค้ด (`trade_mode == 2` -> Block)
2. **Single Position Only:** ไม่มีการเบิ้ลลอต (No Martingale), ไม่มีการเปิดไม้แก้ (No Grid/Recovery Basket) 1 ออร์เดอร์จบในตัวมันเองเสมอ
3. **Never Clamp Lots:** ถ้าระยะ Stop Loss หรือค่าธรรมเนียมทำให้เกินเพดาน 10% ของ Equity ให้ **"ยกเลิกการเทรด (Reject)"** ห้ามลดขนาดล็อตให้ผ่านเกณฑ์
4. **Mandatory Swap Policy (2026-10-05):** ทุกการทดสอบหรือคำนวณสถิติย้อนหลัง ต้องคำนวณค่า Swap เสมอ (Base + Swap และ Stress + Swap)
5. **UTC Timezone Uniformity:** เวลาทุกอย่างต้องเป็น `timezone-aware UTC` ห้ามใช้ Naive Datetime

---

## 6. สภาพแวดล้อมระบบและการรันบน Cloud (Deployment Architecture)

ระบบรองรับการรัน 2 สภาพแวดล้อม:

### ก. เครื่อง Local (macOS ผ่าน Wine)
- ใช้งานสำหรับการวิจัย, Backtest, History Probe, และการทดสอบ Offline Unit Tests
- ควบคุมผ่านคำสั่ง Makefile (`make bot-run`, `make bot-execute`)

### ข. เครื่อง Oracle Linux Cloud VM (`deploy/c22-demo/`)
- ติดตั้งสแต็กจำลอง Windows: **Box64 + Wine + MetaTrader 5 + Python 3.14**
- จัดเตรียม Systemd Services:
  - `c22-oracle-shadow.service`: รันโหมดตรวจจับสัญญาณและตรวจเกตโดยไม่ส่งออร์เดอร์
  - `c22-oracle-execution.service`: สแตนด์บายสำหรับโหมดส่งคำสั่งจริงบน Demo (เมื่อผ่านเกต)
  - `c22-oracle-backup.service` & `timer`: ทำงานสำรองฐานข้อมูล Journal ทุกชั่วโมง

---

## 7. พิธีสารเปิดตลาดวันจันทร์ (Attended Market-Open Protocol - 2026-10-24)

> [!NOTE]
> **Owner Waiver (24 ต.ค. 2026):** เจ้าของระบบอนุมัติการทดสอบ **"Demo Trial แบบมีคนเฝ้า (Attended) + สำรองข้อมูลบน Mac"** ชั่วคราว แทนการรอระบบ Telegram Alert และ Private Cloud อัตโนมัติ

### ขั้นตอนการปฏิบัติการสำหรับ Operator:
1. **เชื่อมต่อ Session เฝ้าระวัง:** รันสคริปต์เฝ้าจอผ่าน SSH Console บน Mac  
   ```bash
   python deploy/c22-demo/attended_session.py
   ```
   (ส่งเสียง Bell แจ้งเตือนเมื่อเกิด Block, Fill, BE, Exit หรือ Error และคอยซิงก์ Snapshot กลับมายังเครื่อง Mac)
2. **ตรวจสอบ Cost Policy:** ยืนยันสเปกบัญชีและอัตราค่าธรรมเนียมล่าสุด  
   ```bash
   python deploy/c22-demo/review_cost_policy.py
   ```
3. **ตรวจสอบความพร้อมก่อนตลาดเปิด:** รันสคริปต์ตรวจสอบสถานะระบบและฟีดราคา  
   ```bash
   python deploy/c22-demo/prepare_market_open.py
   ```
4. **เกณฑ์ตัดสิน (Readiness Gate):** รวบรวมข้อมูล M15 อย่างน้อย 96 แท่ง ข้ามเที่ยงคืน UTC โดยไม่มี Cache Divergence หรือข้อผิดพลาดร้ายแรง

---

## 8. สรุปคำสั่งสำคัญในการปฏิบัติงาน (Operational Cheat-Sheet)

| งาน | คำสั่ง | คำอธิบาย |
| :--- | :--- | :--- |
| **Demo Runtime Tests** | `make test-demo` | รันชุดทดสอบเฉพาะโมดูล Demo Runtime ทั้งหมด (156 tests) |
| **Full Regression Suite** | `make test` | รันชุดทดสอบ Regression ทั้งหมดของโปรเจกต์ (1,036+ tests) |
| **ตรวจ Lint และ Syntax** | `make check` หรือ `make lint` | ตรวจสอบ Syntax และ Code Formatting ทั่วทั้งโปรเจกต์ |
| **รันโหมด Shadow (ไม่ส่งออร์เดอร์)** | `make bot-run` หรือ `make bot-start` | รันบอทตรวจจับสัญญาณและทดสอบ Gate โดย**ไม่ส่งคำสั่งจริง** |
| **รันโหมด Execute (ส่งออร์เดอร์ Demo)** | `make bot-execute` หรือ `make c22h4-run` | รันบอทและ**อนุญาตส่งคำสั่งบน Demo** (เมื่อผ่าน Gate ครบ) |
| **ตรวจสถานะบอท** | `make bot-status` หรือ `make c22h4-status` | ดูสถานะกระบวนการ, Journal ล่าสุด, และสถานะ Gate ปัจจุบัน |
| **หยุดการทำงานของบอท** | `make bot-stop` หรือ `make c22h4-stop` | ปิด Process ของ Watcher อย่างปลอดภัย (ไม่กระทบออร์เดอร์ใน MT5) |
| **Attended Console (Mac)** | `python deploy/c22-demo/attended_session.py` | คอนโซลมีคนเฝ้าพร้อมเสียง Bell เตือนและดาวน์โหลด SQLite Snapshot |
| **ตรวจความพร้อมตลาดเปิด** | `python deploy/c22-demo/prepare_market_open.py` | สคริปต์สรุปความพร้อมก่อนตลาดเปิดวันจันทร์ |
| **สลับกลับไป Rollback** | `make trial30-status` / `make trial30-run` | ตรวจสอบและรันกลยุทธ์ Trial30 เดิมเมื่อต้องการถอยกลับ |
