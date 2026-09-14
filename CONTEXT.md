# CONTEXT: XAUUSD Trading System v2 (SMC Liquidity & Structure Engine)

> **Version:** 2.0-production-hardened  
> **Status:** Production Hardening & Financial Safety Execution  
> **Last Updated:** 2026-09-06  
> **Canonical Source:** Repository Root `CONTEXT.md`

---

## 1. Domain Glossary & Ubiquitous Language

| คำศัพท์ (Domain Term) | นิยามเชิงระบบ (Mathematical / Algorithmic Definition) |
| :--- | :--- |
| **Liquidity Pool** | ระดับราคาที่มี Stop Orders หนาแน่น: อิงจาก **Asian Range H/L (00:00–07:00 UTC)**, **PDH/PDL**, และ **London Session H/L (07:00–12:00 UTC)** สำหรับดักจับใน New York Session |
| **Liquidity Sweep** | การที่ราคาแท่ง M5/M15 ทะลุแนว Liquidity Pool ด้วย **ไส้เทียน (Wick-only)** โดยเนื้อเทียนปิดกลับเข้ามาภายในแนวเดิม และระยะแทงทะลุไม่เกิน **$8.00 (800 points)** |
| **True Swing Extremum** | จุด Invalidation ทางโครงสร้าง: คือจุดต่ำสุดจริง (สำหรับ BUY) หรือจุดสูงสุดจริง (สำหรับ SELL) ของ **แท่งเทียนทั้งหมดระหว่างแท่ง Sweep ถึงแท่ง MSS** ป้องกันการโดนกวาดไส้สอง |
| **Expansion Breakout** | ราคาปิดเนื้อเทียนทะลุแนว หรือทะลุเกิน $8.00 $\rightarrow$ ถือเป็น Breakout จริง **Invalidate การหาจังหวะ Sweep ทันที** |
| **M5 Swing Fractal** | จุดสูงสุด/ต่ำสุดย่อยบน M5 นิยามด้วย **5-bar Fractal** (2 แท่งซ้าย + 1 แท่งกลาง + 2 แท่งขวา) |
| **Market Structure Shift (MSS)** | สัญญาณกลับตัวโครงสร้าง: ราคาแท่ง M5 ต้อง **ปิดเนื้อเทียน (Body Close)** ทะลุผ่าน M5 Swing High ล่าสุด (สำหรับขาขึ้น โดยแท่งเทียนต้องเป็นแท่งเขียว Close > Open) หรือ Swing Low ล่าสุด (สำหรับขาลง แท่งแดง Close < Open) |
| **Displacement** | แท่งเทียนโมเมนตัมที่ยืนยัน MSS โดยสัดส่วนเนื้อเทียน (Body) ต้องมีขนาดอย่างน้อย **45% ของความยาวแท่งทั้งหมด (Total Range)** เพื่อรองรับไส้ของทองคำ |
| **Fair Value Gap (FVG)** | ช่องว่างราคา 3 แท่งเทียน: สำหรับขาขึ้น `candle[i-1].low > candle[i+1].high` ขนาดช่องว่างต้อง **$\ge \$0.30 (30 points)$** |
| **Consequent Encroachment (50% FVG)** | จุดกึ่งกลางของกรอบ FVG $(FVG_{High} + FVG_{Low}) / 2$ ซึ่งเป็นจุดวาง Limit Order |
| **Order TTL (Time-To-Live)** | อายุของ Limit Order: หากราคาไม่ย่อลงมาเกี่ยวภายใน **4 แท่ง (20 นาทีบน M5, 60 นาทีบน M15)** ให้ทำการยกเลิกคำสั่งทันที |
| **Sweep→MSS→FVG Window** | MSS ต้องเกิดภายใน **8 แท่ง** หลังแท่ง Sweep; FVG ต้องเกิดบนแท่ง MSS เอง หรือภายใน 4 แท่งถัดไป |
| **H1 Trend Filter** | H1 Close $> \text{EMA}(200) \rightarrow$ อนุญาตเฉพาะฝั่ง BUY; H1 Close $< \text{EMA}(200) \rightarrow$ อนุญาตเฉพาะฝั่ง SELL |
| **Session Killzones** | London (07:00–10:30 UTC) และ New York (12:30–16:30 UTC) ครอบคลุมช่วง London Fix |
| **Rollover Flat Rule** | บังคับปิดทุก Position ก่อนเวลา 20:55 UTC เพื่อหลีกเลี่ยง Spread ถ่างและ Swap |
| **Two-Tier Scale-Out** | กลไกทำกำไร: เมื่อราคาแตะ **+1.0R** ให้ปิดแบ่งทำกำไร **50% ทันที (PARTIAL_CLOSE)** พร้อมเลื่อน SL ของอีก 50% มาที่ **Breakeven (Entry $\pm$ Spread Buffer)** ปล่อยให้ Runner วิ่งชน **+2.5R (Full TP)** |
| **Max SL Cap** | จำกัดระยะ Stop Loss สูงสุดไม่เกิน **$25.00 (2500 points)** สอดคล้องกับความผันผวนของทองคำที่ราคา $4000-$5200 (หากเกิน Skip Setup) |
| **Strict Small-Account Risk Gate** | หากคำนวณ Lot ได้ต่ำกว่า 0.01 lot แล้วการบังคับเปิด 0.01 lot จะทำให้พอร์ตเสี่ยงเกิน **1.5% ของเงินทุน** ระบบต้อง **ปฏิเสธคำสั่งทันที (is_valid=False)** ห้าม Over-risk เด็ดขาด |
| **News Blackout Window** | ห้ามเปิดออเดอร์ใหม่ก่อน/หลังข่าวแดง USD 30 นาที; หากมีออเดอร์ค้างก่อนข่าว 15 นาที: ถ้ากำไร $\ge 1R$ ให้เลื่อน BE, ถ้ากำไร $< 1R$ ให้ปิดทิ้งทันที |
| **Execution-Notification Coupling** | การ์ดสัญญาณ Telegram และการสั่งออเดอร์ต้องผูกติดกับ OrderIntent ที่ผ่าน Orchestrator แล้วเท่านั้น ห้ามส่งสัญญาณ Phantom Signal เด็ดขาด |
| **Turtle Soup Strategy (TSS)** | การแทงทะลุหลอกระดับ 20-bar Swing High/Low ด้วยไส้เทียน ($0.40–$5.00) แล้วเนื้อเทียนปิดกลับเข้ามาในกรอบเดิม (False Breakout / Liquidity Raid) เข้าสวนทันที |
| **Golden Session Setup (GSS)** | การย่อตัวกลับเข้าสู่โซน Fibonacci 61.8%–78.6% (Optimal Trade Entry - OTE) ของคลื่นส่ง Displacement ในช่วง London/NY Killzone |

---

## 2. Settled Design Decisions (บันทึกข้อตกลงที่ยุติแล้ว)

* **[ADR-001] Liquidity Reference:** (Superceded by ADR-017)
* **[ADR-002] Strict Sweep Rule:** ไส้ทะลุได้ แต่เนื้อเทียนต้องปิดกลับเข้าข้างใน และห้ามทะลุเกิน $8.00
* **[ADR-003] MSS Body Confirmation:** บังคับปิดแท่งด้วย Body Close เหนือ 5-bar Fractal Swing พร้อมทิศทางแท่งเทียนตรงกับฝั่งเทรด
* **[ADR-004] FVG & Displacement Thresholds:** Body $\ge 45\%$ ของแท่ง และ FVG $\ge 30$ points ($0.30)
* **[ADR-005] Limit Entry & Expiration:** เข้าที่ 50% FVG ด้วย Limit Order โดยมีอายุคำสั่ง 4 แท่ง
* **[ADR-006] H1 Direction Bias:** ใช้ H1 Close เทียบกับ EMA 200 เป็นตัวกรองทิศทางเทรด 100%
* **[ADR-007] Session Killzones & Rollover Flat:** สแกนเข้าเทรดเฉพาะ London (07:00-10:30 UTC) & NY (12:30-16:30 UTC) และปิดทุกไม้ก่อน 20:55 UTC
* **[ADR-008] Profit Target & Breakeven:** (Superceded by ADR-018)
* **[ADR-009] SL Spread Buffer & Distance Cap:** (Superceded by ADR-019)
* **[ADR-010] News Blackout & Pre-News Action:** ห้ามเข้าเทรดรอบข่าวแดง 30 นาที และเคลียร์สถานะตามเงื่อนไข $1R$ ก่อนข่าว 15 นาที
* **[ADR-011] Circuit Breaker & Cooldown:** หากเกิด Realized Loss 2 ครั้งใน 1 วัน UTC ให้หยุดเทรดทันทีทั้งวัน; หากโดน SL 1 ไม้ให้ Cooldown 30 นาที
* **[ADR-012] Pure Function Strategy Core:** โมดูล SMC Engine ต้องไม่มีการพึ่งพา MetaTrader5 API ภายใน รับเฉพาะ OHLCV DataFrame เพื่อให้ทดสอบได้ 100% บน Mac
* **[ADR-013] Tri-Channel Copilot & Logging:** แจ้งเตือนผ่าน Telegram (การ์ด + กราฟ Dark Theme) พร้อมบันทึก SQLite Lifecycle และ Google Sheets Sync
* **[ADR-014] Sweep→MSS→FVG Temporal Window:** MSS เกิดภายใน 8 แท่งหลัง Sweep; FVG เกิดภายใน 4 แท่งหลัง MSS
* **[ADR-015] Existing v0 Coexistence:** โมดูล SMC v2 แยกอิสระ ทำงานคู่ขนานกับ v0
* **[ADR-016] M5 Data Requirement:** ระบบทำงานบน M5 (หรือ M15 ในกรณีข้อมูลย้อนหลัง)
* **[ADR-017] Multi-Session Liquidity Cascade:** ใช้ Asian Range H/L (00:00-07:00 UTC), PDH/PDL, และ London H/L (07:00-12:00 UTC) สำหรับดักจับใน New York Session
* **[ADR-018] Two-Tier Scale-Out Architecture:** ปิด 50% ที่ +1.0R (ล็อคกำไรเงินสด), เลื่อน SL มาที่ Breakeven (+0.10 spread buffer), และปล่อย 50% วิ่งชน 2.5R Runner
* **[ADR-019] Gold Dynamic SL Cap & True Swing Extremum:** ขยาย Max SL Cap เป็น $25.00 สำหรับทองคำ และยึด Stop Loss ที่จุดต่ำสุด/สูงสุดจริงของสวิงทั้งหมดระหว่าง Sweep ถึง MSS
* **[ADR-020] Strict Small-Account Risk Gate:** ปฏิเสธคำสั่งทันทีหาก 0.01 lot ทำให้ความเสี่ยงเกิน 1.5% ของเงินทุนในพอร์ต
* **[ADR-021] Execution & Notification Alignment:** ส่งการ์ด Telegram แจ้งเตือนเฉพาะเมื่อ OrderIntent ผ่านการตรวจสอบจาก Orchestrator แล้วเท่านั้น ป้องกัน Phantom Signals
* **[ADR-022] Timezone Uniformity Standard:** ข้อมูลเวลาทั้งหมดในระบบต้องเป็น Timezone-aware UTC ห้ามเปรียบเทียบ offset-naive กับ aware datetime
* **[ADR-023] TradingView Master Copilot Indicator Architecture (Hardened):** พัฒนา indicator บน TradingView Pine Script v6 สำหรับ XAUUSD เพื่อเป็น Visual & Notification Copilot คู่ขนาน รองรับ 3 กลยุทธ์สถาบันแท้จริง (SMC Prime พร้อม 50% FVG Limit + 4-bar TTL, TSS Turtle Soup, GSS Golden Zone OTE ตรวจสอบทิศทางสวิง) ปลด Trend Flow ออกเพื่อป้องกันการขัดแย้งของสัญญาณ ทำงานบน M15/M5 ป้องกัน Repaint ด้วย Zero-Repaint H1 Confirmed Security (`close[1]`), จัดการความเสี่ยงแบบข้ามแพลตฟอร์ม 100% สอดคล้องกับ Python Core (Max SL Cap $25.00 หากเกิน Invalidate Setup ทันที, Two-Tier Scale-Out 1.0R TP1 ปิด 50% บังทุน + 2.5R Runner, London Liquidity Tracking 07:00-12:00 UTC), และ Real-Time Dashboard HUD พร้อมแจ้งเตือนสถานะการเทรดครบวงจร (Setup Pending, Filled, BE Moved, TP/SL Hit)
* **[ADR-024] Live Execution Guardrails & Deterministic Lifecycle Binding:** (1) Conservative SL Invariant: ตรวจ Original SL ก่อนเสมอเมื่อแท่งแตะทั้ง SL และ TP1/TP2 เพื่อกำจัด Survivor Bias (2) Spread-Calibrated Match & Exit: Long limit entry ใช้ low+$0.30 เป็น Ask, Short TP exit ใช้ low+$0.30 เป็น Ask; Short SL ใช้ raw high เพราะ slBuffer บวกไว้แล้ว (3) tp1Bar Runner Guard: ห้ามเช็ค Breakeven SL ในแท่งเดียวกับที่เกิด TP1 เพราะ lower shadow เกิดก่อน expansion (4) Killzone Guard Expiration: ยกเลิก Pending Limit เมื่อพ้น Killzone (หากตั้งไว้ใน KZ) หรือครบ 4 แท่ง (5) Deterministic Order ID: แนบ order_id ทุก Webhook JSON (SETUP_PENDING, ORDER_FILLED, TP1_HIT_MOVE_BE, ORDER_CANCELED, TRADE_CLOSED) สำหรับ MT5 ticket mapping

