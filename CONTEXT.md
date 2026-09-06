# CONTEXT: XAUUSD Trading System v1 (SMC Liquidity & Structure Engine)

> **Version:** 1.0-draft  
> **Status:** Active Foundation Phase (Grilling / Architectural Design)  
> **Last Updated:** 2026-09-06  
> **Canonical Source:** Repository Root `CONTEXT.md`

---

## 1. Domain Glossary & Ubiquitous Language

| คำศัพท์ (Domain Term) | นิยามเชิงระบบ (Mathematical / Algorithmic Definition) |
| :--- | :--- |
| **Liquidity Pool** | ระดับราคาที่มีคำสั่ง Stop Orders หนาแน่น: อิงจาก **Asian Range High/Low (00:00–07:00 UTC)** และ **Previous Day High/Low (PDH/PDL)** |
| **Liquidity Sweep** | การที่ราคาแท่ง M5 ทะลุแนว Liquidity Pool ด้วย **ไส้เทียน (Wick-only)** โดยเนื้อเทียน (Candle Body) ต้องปิดกลับเข้ามาอยู่ภายในแนวเดิม และระยะแทงทะลุต้องไม่เกิน **$5.00 (500 points)** |
| **Expansion Breakout** | ราคาปิดเนื้อเทียนทะลุแนว หรือทะลุเกิน $5.00 $\rightarrow$ ถือเป็น Breakout จริง **Invalidate การหาจังหวะ Sweep ทันที** |
| **M5 Swing Fractal** | จุดสูงสุด/ต่ำสุดย่อยบน M5 นิยามด้วย **5-bar Fractal** (2 แท่งซ้าย + 1 แท่งกลาง + 2 แท่งขวา) |
| **Market Structure Shift (MSS)** | สัญญาณกลับตัวโครงสร้าง: ราคาแท่ง M5 ต้อง **ปิดเนื้อเทียน (Body Close)** ทะลุผ่าน M5 Swing High ล่าสุด (สำหรับขาขึ้น) หรือ Swing Low ล่าสุด (สำหรับขาลง) |
| **Displacement** | แท่งเทียนโมเมนตัมที่ยืนยัน MSS โดยสัดส่วนเนื้อเทียน (Body) ต้องมีขนาดอย่างน้อย **60% ของความยาวแท่งทั้งหมด (Total Range)** |
| **Fair Value Gap (FVG)** | ช่องว่างราคา 3 แท่งเทียน: สำหรับขาขึ้น `candle[i-1].low > candle[i+1].high` โดย `candle[i]` คือแท่ง Displacement ขนาดช่องว่างต้อง **$\ge \$0.50 (50 points)$** |
| **Consequent Encroachment (50% FVG)** | จุดกึ่งกลางของกรอบ FVG $(FVG_{High} + FVG_{Low}) / 2$ ซึ่งเป็นจุดวาง Limit Order |
| **Order TTL (Time-To-Live)** | อายุของ Limit Order: หากราคาไม่ย่อลงมาเกี่ยวภายใน **3 แท่ง M5 (15 นาที)** ให้ทำการยกเลิกคำสั่งทันที |
| **Sweep→MSS→FVG Window** | MSS ต้องเกิดภายใน **6 แท่ง M5 (30 นาที)** หลังแท่ง Sweep; FVG ต้องเกิดบนแท่ง MSS เอง หรือ 2 แท่งถัดไป หากเกินกรอบนี้ถือว่า Sweep หมดอายุ (Invalidate) |
| **H1 Trend Filter** | H1 Close $> \text{EMA}(200) \rightarrow$ อนุญาตเฉพาะฝั่ง BUY; H1 Close $< \text{EMA}(200) \rightarrow$ อนุญาตเฉพาะฝั่ง SELL |
| **Session Killzones** | London (07:00–10:00 UTC / 14:00–17:00 TH) และ New York (12:30–15:30 UTC / 19:30–22:30 TH) |
| **Rollover Flat Rule** | บังคับปิดทุก Position ก่อนเวลา 21:00 UTC (04:00 น. เวลาไทย) เพื่อหลีกเลี่ยง Spread ถ่างและ Swap |
| **Breakeven (BE) Trigger** | เมื่อราคาเดินทางถึง **+1.0R** ให้ย้ายระดับ Stop Loss มาที่จุดเข้าทันที ($\text{Entry} \pm \text{Spread}$) |
| **Max SL Cap** | หากระยะ Stop Loss จาก Entry ไปถึงปลายไส้ Sweep กว้างเกิน **$6.00 (600 points)** ให้ **Skip Trade** ทันที |
| **News Blackout Window** | ห้ามเปิดออเดอร์ใหม่ก่อน/หลังข่าวแดง USD 30 นาที; หากมีออเดอร์ค้างก่อนข่าว 15 นาที: ถ้ากำไร $\ge 1R$ ให้เลื่อน BE, ถ้ากำไร $< 1R$ ให้ปิดทิ้งทันที |
| **Strategy Architecture** | แยกเป็น 2 ชั้น: (1) **Pure Detection** `detect_smc_setup()` — stateless, รับ DataFrame ส่งออก SetupSignal (2) **Stateful Orchestrator** `StrategyOrchestrator.on_bar()` — จัดการ TTL, BE, Circuit Breaker, Position Lifecycle |

---

## 2. Settled Design Decisions (บันทึกข้อตกลงที่ยุติแล้ว)

* **[ADR-001] Liquidity Reference:** ใช้ Asian Range H/L (00:00–07:00 UTC) ร่วมกับ Previous Day High/Low (PDH/PDL) เป็นหลัก
* **[ADR-002] Strict Sweep Rule:** ไส้ทะลุได้ แต่เนื้อเทียน M5 ต้องปิดกลับเข้าข้างใน และห้ามทะลุเกิน $5.00
* **[ADR-003] MSS Body Confirmation:** บังคับปิดแท่งด้วย Body Close เหนือ 5-bar Fractal Swing
* **[ADR-004] FVG & Displacement Thresholds:** Body $\ge 60\%$ ของแท่ง และ FVG $\ge 50$ points ($0.50)
* **[ADR-005] Limit Entry & Expiration:** เข้าที่ 50% FVG ด้วย Limit Order โดยมีอายุคำสั่ง 3 แท่ง M5 (15 นาที)
* **[ADR-006] H1 Direction Bias:** ใช้ H1 Close เทียบกับ EMA 200 เป็นตัวกรองทิศทางเทรด 100%
* **[ADR-007] Session Killzones & Rollover Flat:** สแกนเข้าเทรดเฉพาะ London & NY Killzones และปิดทุกไม้ก่อน 04:00 น. เวลาไทย
* **[ADR-008] Profit Target & Breakeven:** เป้าหมายคงที่ 2.0R โดยมีกลไกย้าย SL กันทุน (BE) ทันทีที่ราคาแตะ 1.0R
* **[ADR-009] SL Spread Buffer & Distance Cap:** วาง SL ห่างปลายไส้ $0.30 (30 pts) และจำกัดระยะ SL สูงสุดไม่เกิน $6.00 (เกินนี้ Skip)
* **[ADR-010] News Blackout & Pre-News Action:** ห้ามเข้าเทรดรอบข่าวแดง 30 นาที และเคลียร์สถานะตามเงื่อนไข $1R$ ก่อนข่าว 15 นาที
* **[ADR-011] Circuit Breaker & Cooldown:** หากเกิด **Realized Loss 2 ครั้งใน 1 วัน UTC** (ไม่ว่าขนาดเท่าไหร่) ให้หยุดเทรดทันทีทั้งวัน; หากโดน SL 1 ไม้ให้ Cooldown 30 นาที
* **[ADR-012] Pure Function Strategy Core:** โมดูล SMC Engine ต้องไม่มีการพึ่งพา MetaTrader5 API ภายใน รับเฉพาะ OHLCV DataFrame เพื่อให้ทดสอบได้ 100% บน Mac
* **[ADR-013] Tri-Channel Copilot & Logging:** แจ้งเตือนผ่าน Telegram (การ์ด + กราฟ Dark Theme) พร้อมบันทึก SQLite Lifecycle และ Google Sheets Sync
* **[ADR-014] Sweep→MSS→FVG Temporal Window:** MSS ต้องเกิดภายใน 6 แท่ง M5 (30 นาที) หลัง Sweep; FVG ต้องเกิดบนแท่ง MSS หรือ 2 แท่งถัดไป; เกินกรอบนี้ Sweep หมดอายุ
* **[ADR-015] Existing v0 Coexistence:** โมดูล SMC v1 (`scripts/smc/`) เป็นระบบใหม่แยกจากระบบ EMA Sniper v0 เดิม (`scripts/strategy.py`); ไม่มี Facade ไม่มีการลบโค้ดเก่า ทั้งสองระบบทำงานคู่ขนาน
* **[ADR-016] M5 Data Requirement:** ระบบทำงานบน M5 เท่านั้น; ข้อมูล CSV ต้องเป็นรูปแบบ `time,open,high,low,close,tick_volume` (MT5 standard); ข้อมูล GC=F futures ที่มีอยู่จะไม่ถูกใช้
