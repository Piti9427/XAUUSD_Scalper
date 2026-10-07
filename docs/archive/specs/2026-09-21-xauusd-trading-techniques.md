# สรุปเทคนิคการทำกำไรจากการเทรดทองคำ (XAUUSD Trading & Profit-Taking Techniques)

> **Version:** 2.0-production-hardened
> **Target Asset:** XAUUSD (Gold / US Dollar)
> **Timeframe:** M5 (Execution) / H1 (HTF Bias)
> **Source Documents:** `CONTEXT.md`, `scripts/smc/`, `tradingview/xauusd_master_pro_v6.pine`

---

## 1. ภาพรวมสถาปัตยกรรมระบบ (Architecture Overview)

ระบบเทรดทองคำในโปรเจกต์นี้ได้รับการออกแบบตามหลักการ **Deep Module Architecture**:
- **Interface เล็ก แต่ Implementation ลึก (Depth)**: Caller (หรือ Backtester / Webhook) ส่งเพียงข้อมูลแท่งราคา OHLCV และสถานะพอร์ต ระบบจะซ่อนอัลกอริทึมการคำนวณทางคณิตศาสตร์, การตรวจจับสวิง, การประเมินสภาพคล่อง และกฎความเสี่ยงทั้งหมดไว้ข้างใน
- **Pure Functional Seam**: โมดูลการตรวจจับสัญญาณ (`scripts/smc/detection.py`) เป็นฟังก์ชันบริสุทธิ์ (Pure Function) ไม่พึ่งพา Broker API หรือ Side Effect ใดๆ ทำให้ทดสอบและจำลองผลลัพธ์ได้อย่างแม่นยำ 100%
- **Leverage & Locality**: เมื่อมีการปรับปรุงค่าพารามิเตอร์หรือตรรกะทำกำไร จะเกิดขึ้นที่ Seam เดียว และส่งผลต่อทั้งระบบแจ้งเตือน (Telegram/TradingView) และระบบส่งออเดอร์อัตโนมัติ (MT5 Execution Adapter)

```
┌────────────────────────────────────────────────────────┐
│               Public Interface (Small Surface)         │
│  evaluate_smc_setup(...) -> SetupDecision              │
│  on_bar(bar, account) -> List[OrderIntent]             │
├────────────────────────────────────────────────────────┤
│                Deep Implementation                     │
│  1. Multi-Session Liquidity Cascade                    │
│  2. Strict Wick-Only Liquidity Sweep Engine            │
│  3. Market Structure Shift (MSS) + Displacement Ratio  │
│  4. FVG 50% Consequent Encroachment Limit Entry        │
│  5. Two-Tier Scale-Out (50% TP1 @ 1.0R + 2.5R Runner)  │
│  6. Session Killzone & Rollover Flat Engine            │
│  7. High-Impact USD News Shield                        │
│  8. Dynamic Financial Risk & Circuit Breaker Gates     │
└────────────────────────────────────────────────────────┘
```

---

## 2. เทคนิคหลักที่ใช้ทำกำไร (Core Profit-Making Strategies)

### 2.1 กลยุทธ์หลัก: SMC Institutional Prime Strategy (Sweep + MSS + FVG)
เป็นกลยุทธ์หลักของระบบที่ดักจับพฤติกรรมของสถาบันการเงิน (Institutional Order Flow) บนทองคำ:

1. **Multi-Session Liquidity Cascade (ADR-017)**:
   - ดักจับสภาพคล่องที่สะสมรอบแนวสำคัญ:
     - **Asian Range High/Low (00:00–07:00 UTC)**
     - **Previous Day High / Previous Day Low (PDH / PDL)**
     - **London Session High/Low (07:00–12:00 UTC)** สำหรับใช้ดักกวาดในรอบตลาดนิวยอร์ก
2. **Strict Wick-Only Liquidity Sweep (ADR-002)**:
   - ตรวจจับการแทงทะลุแนวสภาพคล่องด้วย **ไส้เทียนเท่านั้น (Wick-Only)** โดยมีระยะเจาะทะลุระหว่าง **$0.30 ถึง $8.00 (30–800 points)**
   - **Anti-Breakout Rule**: เนื้อเทียน (Body) ต้องปิดกลับเข้ามาภายในแนวเดิม หากเนื้อเทียนปิดหลุดแนว ถือเป็น *Expansion Breakout* และระบบจะยกเลิกการค้นหา Setup ทันที
3. **Market Structure Shift (MSS) with Displacement (ADR-003, ADR-004)**:
   - ยืนยันการกลับตัวเมื่อราคาแท่ง M5 ปิดเนื้อเทียนทะลุ **5-bar Fractal Swing** ล่าสุด
   - **Displacement Filter**: สัดส่วนเนื้อเทียน ($\text{Body} / \text{Total Range}$) ต้องมีขนาด **$\ge 45\%$** เพื่อกรองแท่งไร้พลังและรองรับไส้ผันผวนของทองคำ
   - **Temporal Window (ADR-014)**: MSS ต้องเกิดขึ้นภายใน **8 แท่ง** หลังการ Sweep
4. **Fair Value Gap (FVG) & 50% Consequent Encroachment (ADR-004, ADR-005)**:
   - เกิดช่องว่างราคา 3 แท่งเทียน โดยมีขนาดความกว้าง **$\ge \$0.30$ (30 points)**
   - **Limit Order Entry**: วางคำสั่ง Buy Limit / Sell Limit ที่จุดกึ่งกลางของช่องว่าง FVG (50% Consequent Encroachment) เพื่อได้ราคาที่ได้เปรียบที่สุด
   - **Order TTL (Time-To-Live)**: หากราคาไม่ย่อลงมาเกี่ยวคำสั่งภายใน **4 แท่ง (20 นาทีบน M5)** คำสั่งจะถูกยกเลิกทันทีเพื่อป้องกันการเข้าตกรถ
5. **Higher Timeframe Trend Filter (ADR-006)**:
   - กรองด้วยเส้นค่าเฉลี่ย **H1 EMA 200**:
     - $\text{Price} > \text{EMA}(200) \rightarrow$ อนุญาตเฉพาะฝั่ง **BUY**
     - $\text{Price} < \text{EMA}(200) \rightarrow$ อนุญาตเฉพาะฝั่ง **SELL**
   - คำนวณจากแท่งปิดของ H1 ป้องกันปัญหา Repaint

---

### 2.2 กลยุทธ์เสริม: Turtle Soup Strategy (TSS)
- **Concept**: กลยุทธ์ False Breakout แบบดั้งเดิมที่เหมาะกับพฤติกรรมทองคำสะบัดหลอก
- **Trigger**: ราคาทำ New High หรือ New Low ทะลุกรอบ **20 แท่งย้อนหลัง (20-bar Extremum)** ด้วยระยะไส้เทียน **$0.40 – $5.00** แล้วเนื้อเทียนปิดกลับเข้ามาในกรอบ
- **Action**: เข้าออเดอร์สวนทันที (Mean-Reversion Scalp) ภายในช่วง Killzone

---

### 2.3 กลยุทธ์เสริม: Golden Session Setup (GSS / OTE)
- **Concept**: ดักเข้าตามแนว Fibonacci Retracement ในช่วงคลื่นส่งของตลาดทอง
- **Trigger**: เมื่อเกิดคลื่น Impulse Leg ขนาดใหญ่ ($\ge \$3.00$) แล้วราคาย่อตัวกลับเข้าสู่โซน **Optimal Trade Entry (OTE) 61.8% – 78.6% Fibonacci**
- **Action**: ยืนยันด้วยแท่งเทียนกลับตัว (Bullish/Bearish Confirmation) ร่วมกับเทรนด์ H1 EMA 200

---

### 2.4 เครื่องมือยืนยัน: SMT Divergence (Smart Money Tool)
- ตรวจจับความไม่สอดคล้องระหว่างราคาทองคำ (**XAUUSD**) กับดัชนีดอลลาร์ (**DXY**):
  - *Bullish SMT*: ทองคำทำจุดต่ำสุดใหม่ (Lower Low) แต่ DXY ไม่สามารถทำจุดสูงสุดใหม่ (Fails to make Higher High) $\rightarrow$ ยืนยันแรงซื้อทองคำ

---

## 3. กลไกการเก็บกำไรและการบริหารออเดอร์ (Profit-Taking & Order Lifecycle)

### 3.1 สถาปัตยกรรม Two-Tier Scale-Out (ADR-018, ADR-024)
ระบบไม่ใช้การออกไม้เดียวทั้งก้อน แต่แบ่งการปิดกำไรออกเป็น 2 ชั้น เพื่อสร้างความได้เปรียบทางคณิตศาสตร์:

| ชั้นการทำกำไร | เป้าหมายราคา | พฤติกรรมระบบ (System Action) | วัตถุประสงค์ (Rationale) |
| :--- | :--- | :--- | :--- |
| **Tier 1 (TP1)** | **+1.0R** | ปิดแบ่งทำกำไร **50% ทันที (PARTIAL_CLOSE)** | ล็อคกำไรเงินสดเข้าพอร์ตทันที ลดความเสี่ยงทางจิตวิทยา |
| **Breakeven (BE)** | **Entry $\pm \$0.10$** | เลื่อน SL ของไม้ที่เหลือ 50% มาที่ **ทุน + Buffer $0.10** | เปลี่ยนสถานะพอร์ตให้กลายเป็น **Risk-Free Trade 100%** |
| **Tier 2 (Runner)** | **+2.5R** หรือ **Opposing Pool** | ปล่อยให้ 50% ที่เหลือวิ่งชน **2.5R** หรือแนวต้านถัดไป | ดึงผลตอบแทนก้อนใหญ่จากเทรนด์ยาวของทองคำ |

```
Entry (50% FVG) ──────────────────────────────────────────────┐
                                                              │ +1.0R: ปิด 50% (Lock Cash)
                                                              ▼ พร้อมเลื่อน SL -> Breakeven
Stop Loss ───────► เลื่อนมาที่ Entry + $0.10 Buffer ─────────┤
                                                              │
                                                              │ +2.5R: ปิดที่เหลือ 50% (Full TP)
                                                              ▼
```

### 3.2 กฎความเสี่ยงและการป้องกันจุดตัดขาดทุน (Stop Loss Mechanics)
- **True Swing Extremum (ADR-019)**: จุดวาง Stop Loss ไม่ใช่วางสุ่ม แต่ยึดที่ **จุดต่ำสุด/สูงสุดจริงของสวิงทั้งหมดระหว่างแท่ง Sweep ถึงแท่ง MSS** ป้องกันการโดนกวาดไส้สอง
- **Max SL Cap ($25.00 / 2,500 points)**: หากจุดตัดขาดทุนตามโครงสร้างอยู่ห่างเกิน $25.00 ระบบจะ **ปฏิเสธคำสั่งทันที (Skip Setup)** เพื่อไม่ให้เปิดความเสี่ยงกับความผันผวนผิดปกติ
- **Spread-Calibrated Exits**: การคำนวณราคาปิดออเดอร์ Short จะบวกค่า Spread จำลอง $0.30 (30 points) เสมอ เพื่อสะท้อนราคา Ask จริงของโบรกเกอร์

---

## 4. ตัวกรองเวลาและข่าวสาร (Session Killzones & News Shields)

### 4.1 Session Killzone Engine (ADR-007)
ระบบอนุญาตให้ส่งคำสั่งเฉพาะช่วงเวลาที่มีวอลุ่มและสภาพคล่องสูงสุดของโลก:
- **London Killzone**: 07:00 – 10:30 UTC (14:00 – 17:30 น. ตามเวลาไทย)
- **New York Killzone**: 12:30 – 16:30 UTC (19:30 – 23:30 น. ตามเวลาไทย)
- **Judas Swing Window**: 07:00 – 08:30 UTC ช่วงดักทางราคาหลอกก่อนเข้าเทรนด์จริง

### 4.2 Rollover Flat Rule (ADR-007)
- **เวลาบังคับปิด**: **20:55 UTC** (03:55 น. เวลาไทย)
- ปิดทุก Position และยกเลิก Pending Orders ทั้งหมดก่อนตลาดเปลี่ยนวัน เพื่อหลีกเลี่ยง:
  - สเปรดถ่างรุนแรง (Widening Spread)
  - ค่าธรรมเนียมถือข้ามคืน (Overnight Swap Fees)

### 4.3 High-Impact News Blackout Window (ADR-010)
- **ช่วงหยุดเทรด**: ห้ามเปิดออเดอร์ใหม่ก่อนและหลังข่าวสำคัญระดับสีแดงของค่าเงิน USD (CPI, NFP, FOMC, PPI) **30 นาที**
- **การจัดการออเดอร์ที่มีอยู่ก่อนข่าว 15 นาที**:
  - หากออเดอร์มีกำไร $\ge 1.0R \rightarrow$ เลื่อน SL มาที่ Breakeven
  - หากออเดอร์มีกำไร $< 1.0R \rightarrow$ บังคับปิดทำกำไร/ตัดขาดทุนทันที (Flatten Position)

---

## 5. การบริหารเงินทุนและระบบตัดวงจร (Capital Preservation & Circuit Breakers)

1. **Fixed Risk Sizing (0.5% - 1.0%)**: คำนวณ Lot Size อัตโนมัติจากระยะห่าง SL ตามสูตร:
   $$\text{Lot Size} = \frac{\text{Account Balance} \times \text{Risk \%}}{\text{SL Distance (\$) } \times 100}$$
2. **Strict Small-Account Risk Gate (ADR-020)**:
   - หากพอร์ตมีขนาดเล็กจนขนาด Lot ขั้นต่ำ 0.01 lot ทำให้ความเสี่ยงเกิน **1.5% ของพอร์ต** ระบบจะ **ปฏิเสธคำสั่งทันที** ห้าม Over-risk เด็ดขาด
3. **Daily Loss Circuit Breaker (ADR-011)**:
   - หากพอร์ตขาดทุนสะสมถึง **2 ครั้งใน 1 วัน (UTC)** $\rightarrow$ **ระบบจะหยุดเทรดทันทีทั้งวัน (Shutdown for the day)**
   - หากขาดทุน 1 ไม้ $\rightarrow$ พักระบบ (Cooldown) 30 นาที

---

## 6. สรุป Codebase Mapping (ตำแหน่งไฟล์ที่รับผิดชอบแต่ละส่วน)

| ฟังก์ชัน / เทคนิค | โมดูลในโค้ดเบส (Module & Seam) | หน้าที่หลัก |
| :--- | :--- | :--- |
| **Liquidity & Pools** | [`scripts/smc/liquidity.py`](../../scripts/smc/liquidity.py) | คำนวณ Asian Range, PDH/PDL, London Levels |
| **Structure & MSS** | [`scripts/smc/structure.py`](../../scripts/smc/structure.py) | 5-bar Fractal, CHoCH, Displacement, Wick Sweep |
| **Pure Detection Engine** | [`scripts/smc/detection.py`](../../scripts/smc/detection.py) | รวบรวมเงื่อนไขทั้งหมด คืนผลเป็น `SetupDecision` |
| **Order Orchestrator** | [`scripts/smc/orchestrator.py`](../../scripts/smc/orchestrator.py) | State Machine จัดการ Order TTL, TP1, Breakeven, TP2 |
| **Capital & Sizing** | [`scripts/smc/risk.py`](../../scripts/smc/risk.py) | คำนวณ Lot, Risk Gate 1.5%, SL Cap $25 |
| **Circuit Breakers** | [`scripts/smc/risk_halt.py`](../../scripts/smc/risk_halt.py) | ตรวจสอบจำนวนไม้แพ้ต่อวัน และควบคุม Drawdown |
| **News Filter** | [`scripts/smc/news.py`](../../scripts/smc/news.py) | ปฏิทินข่าวสาร และสั่งการก่อนข่าวแดง 15 นาที |
| **TradingView Script** | [`tradingview/xauusd_master_pro_v6.pine`](../../tradingview/xauusd_master_pro_v6.pine) | สคริปต์หน้าจอ indicator และส่ง Webhook สัญญาณคู่ขนาน |
