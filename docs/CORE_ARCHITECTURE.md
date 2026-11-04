# สถาปัตยกรรมแกนกลางของระบบ (Core Runtime Engine Architecture)

> **ปรัชญาการออกแบบ:** **Strategy เปลี่ยนได้เสมอ แต่ Core Engine ต้องคงกระพัน**  
> ไม่ว่าจะเปลี่ยน Logic ไปเป็น Breakout, Trend-Following, Reversal, หรือโมเดลตัวเลขใดๆ กลยุทธ์ทั้งหมดเป็นเพียง **"Pluggable Adapter"** ที่มาเสียบเข้ากับ **"Core Runtime Engine"** (`scripts/demo_runtime/`)  
> หน้าที่ของ Core คือการรับประกันความปลอดภัยของพอร์ต (Safety), วงรอบการทำงาน (Cycle), การกระทบยอดคำสั่ง (Reconciliation), และการจัดการความเสี่ยง (Risk Gate)

---

## 1. ผังการทำงานแกนกลาง (Core Engine vs Strategy Seam)

```mermaid
flowchart TD
    subgraph Data Pipeline [1. Market Data Seam]
        MT5[Broker Feed M1] --> M1Validator[market_data.py: Closed M1 Only]
        M1Validator --> M15Assembler[pure_b1.broker_data: ประกอบครบ 15/15 นาที]
    end

    subgraph Pluggable Strategy [2. Strategy Adapter Seam]
        M15Assembler --> StrategyAdapter["Strategy Adapter (C22, Trial30, หรือกลยุทธ์ใหม่)\n- frame(): ทิศทางสัญญาณ BUY/SELL\n- levels(): ระดับ Entry, SL, TP (ATR หรือ Formula)\n- protects(): กฎ Break-Even"]
    end

    subgraph Core Runtime Engine [3. Core Engine (scripts/demo_runtime/)]
        StrategyAdapter --> Admission[admission.py: Gatekeeper ตรวจสอบความเสี่ยง]
        Admission --> Intent[journal.py: บันทึก Intent ลง SQLite ก่อนส่งคำสั่ง]
        Intent --> Dispatch[broker.py: MT5 OrderSend / Demo Guard]
        Dispatch --> Lifecycle[lifecycle.py: Reconcile ตั๋ว, คุม SL ไม่ให้กว้างขึ้น, Safety Close]
    end

    subgraph Durability & Operations [4. Resilience & Outbox]
        Lifecycle --> SQLite[(c22h4-demo.sqlite3)]
        SQLite --> Outbox[delivery.py: Non-blocking Outbox & HTTP Deadlines]
        SQLite --> Backup[backup.py: Atomic SQLite Vacuum & 7 Snapshots]
        SQLite --> Evidence[evidence.py: สถิติ Prospective PnL & Drawdown]
    end
```

---

## 2. เสาหลักทั้ง 5 ของ Core Engine (The 5 Core Pillars)

### เสาหลักที่ 1: Data Integrity Pipeline (การรับรองความถูกต้องของแท่งราคา)
*ไฟล์หลัก:* [`scripts/demo_runtime/market_data.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/market_data.py) และ [`scripts/pure_b1/broker_data.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/pure_b1/broker_data.py)

1. **ห้ามใช้ Forming Bar เด็ดขาด:** การตัดสินใจต้องเกิดจากแท่งเทียนที่ **"ปิดสมบูรณ์แล้วเท่านั้น"** (Closed Bars)
2. **การประกอบแท่ง 15/15:** แท่ง M15 จะถูกสร้างขึ้นก็ต่อเมื่อมีแท่ง M1 Bid ครบทั้ง 15 นาที หากขาดแม้แต่นาทีเดียว (เช่น ช่วง Rollover หรือเน็ตหลุด) ระบบจะปฏิเสธไม่ส่งแท่งนั้นเข้า Strategy
3. **Causal Bar Cache:** เก็บ Cache แท่งราคาแบบ Deterministic ย้อนหลัง หากข้อมูลจาก Broker เกิด Divergence ระบบจะสั่ง Rebuild ทันที

---

### เสาหลักที่ 2: The Admission Gatekeeper (ระบบคัดกรองความเสี่ยงก่อนส่งคำสั่ง)
*ไฟล์หลัก:* [`scripts/demo_runtime/admission.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py) และ [`scripts/demo_runtime/costs.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/costs.py)

ต่อให้ Strategy สร้างสัญญาณ BUY หรือ SELL หน้าที่ของ Admission คือการตรวจสอบสิทธิ์และงบความเสี่ยงก่อนส่งคำสั่งจริง:

1. **Single Position Limit:** ห้ามเปิด Position พร้อมกัน หากมีไม้ค้างอยู่ ปฏิเสธสัญญาณใหม่ทันที (No Overlapping Trades)
2. **Per-Trade Risk Cap (เพดานเสี่ยงต่อไม้):**
   $$\text{Total Risk} = (\text{Distance to SL} + \text{Slippage Allowance}) \times \text{Contract Size} \times \text{Lot} + \text{Commission}$$
   หาก $\text{Total Risk} > \text{Equity} \times \text{Risk Cap (e.g. 10\%)}$ ระบบจะ **Reject ทันที ห้ามลดขนาดล็อต (Never Clamp Lot)**
3. **Daily Loss Circuit Breaker (เพดานขาดทุนรายวัน):** คำนวณจาก Day-Start Equity ณ วินาทีแรกของวัน UTC หากขาดทุนถึงลิมิต ระบบจะสั่งหยุดรับคำสั่งใหม่ตลอดทั้งวันที่เหลือ
4. **Cost Attestation Validity:** ต้นทุนแฝง (Spread, Slippage, Commission, Swap) ต้องผ่านการรับรองโดย Operator มีอายุไม่เกินที่กำหนด (เช่น 24 ชม. สำหรับ Cutover / 168 ชม. สำหรับ Runtime V2) หากเอกสารหมดอายุ บอทจะไม่เปิดคำสั่ง

---

### เสาหลักที่ 3: Write-Ahead Intent & State Machine (การบันทึกเจตนารมณ์ก่อนส่งคำสั่ง)
*ไฟล์หลัก:* [`scripts/demo_runtime/journal.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/journal.py)

เพื่อป้องกันความผิดพลาดกรณีไฟดับหรือเน็ตหลุดระหว่างส่งคำสั่ง:

1. **บันทึก Intent ก่อนส่ง (Write-Ahead Logging):** ระบบจะเขียนสถานะ `SENDING` พร้อมพารามิเตอร์ทั้งหมดลง SQLite ก่อนที่จะเรียกใช้ API `order_send()` ของ Broker
2. **สถานะ UNKNOWN เมื่อคำตอบไม่ชัดเจน:** หากส่งคำสั่งแล้วหลุดหรือ Timeout ระบบจะไม่ส่งซ้ำ (ห้ามเสี่ยง Double Send) แต่จะบันทึกสถานะเป็น `UNKNOWN` เพื่อรอการ Reconcile ตั๋วในรอบถัดไป
3. **Single-Writer Lock:** ล็อกไฟล์ด้วย Local File Lock ระดับ Process เพื่อป้องกันการเปิดโปรเซสซ้อนทับกันบนบัญชีเทรดเดียวกัน

---

### เสาหลักที่ 4: Broker Reconciliation & Lifecycle Engine (การควบคุมวงจรชีวิตออร์เดอร์)
*ไฟล์หลัก:* [`scripts/demo_runtime/lifecycle.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/lifecycle.py) และ [`scripts/demo_runtime/broker.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/broker.py)

เมื่อคำสั่งถูกเปิดในตลาด Core Engine มีหน้าที่คอยเฝ้าและกระทบยอดบัญชี:

1. **Stable Position Identification:** ค้นหาและผูกออร์เดอร์ด้วย Identifier ที่มั่นคง ไม่พึ่งพาเพียง Comment หรือ Magic Number เพียงอย่างเดียว
2. **Non-Widening SL Protection (กฎห้ามขยาย Stop Loss):** ในทุกรอบ Cycle สถานะ `FILLED` ระบบจะตรวจสอบระดับ SL หากพบว่า SL กว้างขึ้นกว่าสัญญาเดิม หรือความเสี่ยงเกินงบ ระบบจะสั่ง **Safety Close** ทันที
3. **Break-Even (BE) Engine:** หากราคาวิ่งถึงระดับคุ้มทุนตามที่กำหนดใน Strategy จะดำเนินการส่งคำสั่งเลื่อน SL ไปยังจุดคุ้มทุน
4. **Safety Close (ระบบตัดขายฉุกเฉิน):** หากตรวจพบ Position แปลกปลอม (Foreign Exposure) หรือพบข้อผิดพลาดของ Contract ระบบจะสั่งปิด Position นั้นทิ้งทันที และหยุดระบบ (Safety Halt)
5. **Demo Identity Guard:** ตรวจสอบโหมดบัญชี หากตรวจพบว่าเป็นบัญชีจริง (`trade_mode == 2`) จะสั่ง Fail-Closed ทันที

---

### เสาหลักที่ 5: Durability, Delivery & Observability (ความคงทนและการแจ้งเตือน)
*ไฟล์หลัก:* [`scripts/demo_runtime/delivery.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/delivery.py), [`scripts/demo_runtime/backup.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/backup.py), [`scripts/demo_runtime/evidence.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/evidence.py)

1. **Non-blocking Outbox Queue:** ข้อความแจ้งเตือน (Telegram / Healthchecks) ถูกจัดเก็บลงตาราง Outbox ใน SQLite และส่งแบบ Asynchronous โดยมีขีดจำกัด Deadline ชัดเจน ไม่ทำให้รอบการเทรดของบอทสะดุด
2. **Atomic Backup & Checksum:** สำรองข้อมูลฐานข้อมูล SQLite อัตโนมัติด้วยคำสั่ง `VACUUM INTO` คำนวณ SHA256 Checksum และหมุนเวียนเก็บ 7 Snapshot ล่าสุด
3. **Prospective Evidence:** บันทึกและประเมินผลกำไร/ขาดทุนสุทธิ (Net PnL, Expectancy, Profit Factor, Equity Drawdown) โดยแยกผลลัพธ์การเทรดปกติ ออกจากผลลัพธ์การตัดขายฉุกเฉิน (Containment)

---

## 3. สัญญาการเชื่อมต่อของ Strategy (The Strategy Interface Seam)

เมื่อคุณต้องการพัฒนาหรือเปลี่ยน Strategy ใหม่เข้ามาในอนาคต Strategy นั้นต้องสร้างเป็นคลาสที่ส่งมอบ Interface ต่อไปนี้ให้กับ Core Engine:

```python
class StrategyInterface:
    magic: int                 # หมายเลข Magic ประจำกลยุทธ์
    snapshot: str              # รหัส Snapshot / Git commit ที่ตรึงสัญญา
    risk_cap: float            # เพดานความเสี่ยงสูงสุดต่อไม้ (เช่น 0.10 สำหรับ 10%)
    
    def frame(self, m15_bars, h4_bars) -> dict:
        """
        ตรวจจับสัญญาณจากแท่งราคาที่ปิดสมบูรณ์แล้ว
        Return: {"direction": 1 (BUY) หรือ -1 (SELL) หรือ 0 (ไม่มีสัญญาณ)}
        """
        ...
        
    def levels(self, direction: int, quote: dict, atr: float) -> dict:
        """
        คำนวณระดับราคา Entry, Stop Loss และ Take Profit
        Return: {"entry": float, "sl": float, "tp": float}
        """
        ...
        
    def protects(self, direction: int) -> bool:
        """
        กำหนดว่าฝั่งนี้ใช้งาน Break-Even หรือไม่ (True/False)
        """
        ...
```

เมื่อเขียน Adapter เสร็จ สามารถนำไปเสียบเข้ากับ `DemoRunner` ได้ทันที:
```python
runner = DemoRunner(strategy=MyNewStrategy(), journal_path="data/my_bot.sqlite3")
runner.cycle(now=clock_now())
```

---

## 4. กฎเหล็กประจำ Core System ที่ไม่มีวันเปลี่ยนแปลง (Non-Negotiable Invariants)

1. **Zero Real Money:** ระบบนี้ไม่รองรับการเทรดเงินจริง และมีตัวบล็อกบัญชีจริงในระดับโค้ด
2. **Single Position Only:** ไม่มีการเบิ้ลลอต (No Martingale), ไม่มีการเปิดไม้แก้ (No Grid/Recovery Basket) 1 ออร์เดอร์จบในตัวมันเองเสมอ
3. **Never Clamp Lots:** ถ้าระยะ Stop Loss หรือค่าธรรมเนียมทำให้เกินเพดาน 10% ของ Equity ให้ **"ยกเลิกการเทรด (Reject)"** ห้ามลดขนาดล็อตให้ผ่านเกณฑ์
4. **Mandatory Swap Policy:** ทุกการทดสอบหรือคำนวณสถิติย้อนหลัง ต้องคำนวณค่า Swap เสมอ (Base + Swap และ Stress + Swap)
5. **UTC Timezone Uniformity:** เวลาทุกอย่างต้องเป็น `timezone-aware UTC` ห้ามใช้ Naive Datetime
