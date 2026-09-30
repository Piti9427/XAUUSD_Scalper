# Core Trading Strategy & Logic (Single Source of Truth)

**Last Updated:** 2026-09-29
**Status:** Research target (Pure B1 Single-Position); live execution NO-GO

เอกสารนี้คือ contract ของ Pure B1 ที่อยู่ระหว่างวิจัย ไม่ใช่คำยืนยันว่าทางเดิน live ใช้กติกานี้แล้ว **หากมีการเปลี่ยนแปลงเงื่อนไขการเทรดใดๆ Agent ทุกตัวต้องมาอัปเดตไฟล์นี้ทุกครั้ง**

---

## 1. ข้อมูลพื้นฐาน (Basic Info)
*   **Symbol:** XAUUSD (Gold); target Exness Demo ใช้ symbol ที่ terminal ยืนยัน (`XAUUSDm` ใน archived capture)
*   **Timeframe:** M15 (กราฟ 15 นาที)
*   **Capital Base:** $200 (Micro-account)
*   **Data/Execution target:** ใช้ Bid OHLC ของ UTC M15 ที่รวมจาก M1 ครบ 15/15 นาทีตาม archived replay; หลังปิดแท่งจึงใช้ quote ใหม่ โดย BUY entry Ask / SELL entry Bid. Direct MT5 M15 อาจมีแท่งช่วงตลาดพักที่ reference ไม่รับ. มี read-only Shadow entrypoint แต่ยังไม่มี broker fill หรือ live order path ของ Pure B1

---

## 2. ลอจิกการเข้าเทรด (Entry Logic - Pure B1)
ระบบใช้เงื่อนไข Price Action ผสมกับ Indicator โดยต้องผ่านด่านตรวจ (Gates) ดังนี้:

1.  **Donchian breakout (30):** ราคาปิดทะลุ high/low ของ 30 แท่งก่อนหน้า (ไม่รวมแท่งสัญญาณ)
2.  **RSI Guard (14):** RSI ต้องมากกว่า 30 และน้อยกว่า 70 ทั้ง BUY และ SELL
3.  **EMA Trend Filter (50):**
    *   อนุญาตให้เทรดฝั่ง **BUY** เฉพาะเมื่อราคาปิด *อยู่เหนือ* EMA 50 เท่านั้น
    *   อนุญาตให้เทรดฝั่ง **SELL** เฉพาะเมื่อราคาปิด *อยู่ใต้* EMA 50 เท่านั้น

`scripts/strategy.py:pure_b1_bars` นิยาม indicator ที่ต้องเทียบให้ตรง: prior high/low ใช้ rolling 30 แล้ว shift 1; RSI14 คำนวณ gain/loss ด้วย EWM span 14, `adjust=False`; EMA50 ใช้ EWM span 50, `adjust=False`; ATR14 เป็น rolling mean ของ true range. `scripts/pure_b1/broker_data.py:completed_m15_from_m1` กรองแท่ง M15 ที่ M1 ไม่ครบเช่นเดียวกับ `scripts/research/data.py:bars`. การดึงแท่งใหม่ต้องรักษา UTC index และ warmup/state ให้ตรงกับ replay; ช่วงต้นข้อมูลที่ indicator ยังไม่พร้อมไม่มี signal.

---

## 3. การจัดการความเสี่ยงและต้นทุน (Risk & Fee Math)
Pure B1 ใช้ fixed 0.01 lot เท่านั้น ตรวจความเสี่ยงจาก Stop Loss และต้นทุนแฝงของ Broker (Spread + Commission + Slippage) ก่อนส่งคำสั่ง ห้ามเพิ่ม lot อัตโนมัติ

*   **Take Profit (TP):** 6.25 ATR
*   **Stop Loss (SL):** 2.5 ATR
*   **Pure B1 risk policy:** fixed 0.01 lot ผ่านเมื่อความเสี่ยงรวมไม่เกิน 10% ของ equity; ถ้าเกิน **ปฏิเสธออร์เดอร์** ไม่ลด/เพิ่ม lot
*   **Legacy webhook policy:** `webhook.risk_pct: 0.05` ยังเป็น sizing budget ของ SMC webhook เดิม ไม่ใช่เกณฑ์ปฏิเสธ Pure B1
*   **สมการต้นทุน (Cost Model):**
    `fixed_lot_risk = 0.01 * ((abs(entry - SL) + spread_buffer + slippage_allowance) * contract_size + commission_per_lot)`
    Live gate ต้องใช้ broker-side entry/SL, equity และ symbol contract/volume จริง พร้อม cost model; ไม่บวก spread ซ้ำถ้าราคา entry/SL รวม spread แล้ว

---

## 4. การจัดการออร์เดอร์ (Position & Recovery Management)
*   **Recovery:** ❌ **ปิดการใช้งาน (DISABLED)**
    *   ระบบนี้เป็นไม้เดี่ยว (Single-Position) 100%
    *   ไม่มีการเบิ้ลลอต (No Martingale), ไม่มีการเปิดไม้แก้ (No Grid/Recovery)
    *   อิงตามผล Backtest วันที่ 2026-09-28: โลจิก Breakout แบบแก้ไม้นั้นขัดแย้งกันเองทางคณิตศาสตร์
*   **Daily Circuit Breaker:**
    *   จำกัดการขาดทุนสะสมต่อวัน UTC ไม่เกิน 40% ของ day-start equity (ประมาณ $80 เมื่อเริ่มที่ $200); หากชนเกตให้หยุดรับไม้ใหม่จนวันถัดไป. Shadow รับ baseline เฉพาะ snapshot ในวินาทีแรกของ 00:00 UTC เก็บข้าม restart และปฏิเสธเมื่อ baseline หายหรือ balance เปลี่ยน. Snapshot นี้ยังไม่พิสูจน์ floating equity ตรงขอบเวลาแบบ exact; ต้องประเมินข้อจำกัดก่อนใช้กับ order path.
*   **Shadow broker gates:** ตรวจบัญชี Demo USD แบบ hedging, quote age, symbol trade mode, stop/freeze distance, volume 0.01, margin และ broker profit calculation จาก snapshot. Cost policy เป็น operator-attested พร้อม account fingerprint, evidence SHA-256, commission USD/lot round trip และ slippage allowance; ไม่ใช่หลักฐาน fills หรือสถานะ swap-free ย้อนหลัง. ไม่มี `order_send` ใน Shadow.

## 5. ขอบเขตหลักฐานและการยืนยันผลลัพธ์ (Evidence)

กฎในเอกสารนี้เป็น **research target ที่เลือกศึกษา**; ยังไม่ใช่กลยุทธ์ที่ผ่านเกต Demo automation หรือเงินจริง. ผลย้อนหลังแต่ละชุดต้องระบุ signal, data source, fill/cost model และ risk admission; ห้ามนำผลคนละ contract มาเป็นผลของ target.

1. **ผล OHLC 2.7 ปี +700.4%:** งานคัดเลือกย้อนหลังใช้ public Dukascopy-derived Bid-only bars, entry ที่ signal-bar close และ flat USD 0.30 cost. ไม่มี Exness Bid/Ask fill, slippage, margin approval, swap-free history หรือ broker deal ledger จึงใช้เป็น research screening เท่านั้น. ตัวเลขนี้ไม่พิสูจน์ว่า EMA/RSI จำเป็นหรือทำกำไรได้ภายใต้บัญชีเป้าหมาย. ดู [broker conditions audit](docs/reviews/2026-09-29-xauusdm-broker-conditions-audit.md).
2. **ผล archived Exness tick +341.99%:** ใช้ RSI BUY ≤75 / SELL ≥25 และ **ไม่มี EMA50**; ไม่ใช่ signal contract ในเอกสารนี้. เป็น Python replay ไม่ใช่ order ที่ broker รับและ fill.
3. **ผล target บน Exness ticks ชุดเดียวกัน:** strict RSI 30–70 + EMA50 ได้ **-33.51%** ภายใต้ spread-only และ cost-inclusive 10% cap (4 trades). กรณีสมมติ fee 0.10R พร้อม current-spec swap ได้ **+150.31%** (49 trades) เพราะ fee เปลี่ยนการรับไม้และเส้นทาง equity; ไม่ใช่ค่าธรรมเนียม Standard ที่วัดจริง. ทั้งสองกรณียังไม่วัด broker slippage, margin approval และ historical swap entitlement. แหล่งตัวเลขและ hash ของ input/source: [target replay verdict](docs/reviews/2026-09-29-pure-b1-target-replay-verdict.md) กับ `data/b1_pure_target_replay_cost_gated_2026_09_29/contract.json`.
4. **มติปัจจุบัน:** เลือก Donchian 30 + RSI 30–70 + EMA50, TP 6.25 ATR / SL 2.5 ATR, fixed 0.01 lot, 10% cap, daily 40% เป็น contract เป้าหมาย **เพื่อวิจัยต่อ**. ทำ data/replay parity และ read-only Shadow ได้ตาม [แผน](.cursor/plans/pure_b1_go-live_6dcb0773.plan.md); Demo orders และเงินจริงต้องผ่านเกตและมติแยก. `main.py` ยังรัน legacy wick strategy ไม่ใช่ Pure B1.


## 6. Offline logic tuning loop (2026-09-30)

Research implementation: `scripts/research/tune_breakout_logic.py` and
`scripts/research/breakout_logic.py`; no order or notification API.
Baseline remains Donchian 48 / ATR14 / SL 2.5 ATR / TP 3 ATR, RSI/EMA off,
fixed 0.01 lot, 10% cost-inclusive equity cap, UTC daily admission halt 40%.
This is an experimental comparator, not a replacement for the frozen target above.

143 unique research combinations tested: immediate/confirm/retest entry,
failed-breakout exit after one/two closes, reset after exit, 4/8/16-bar
no-progress exit, and ATR versus structural SL. Structural SL uses original
breakout and entry candle extremes plus one tick; invalid or over-cap entries
are rejected, never clamped. Protective exits use first available quote after
close even when entry-lateness gate would reject a new entry. Entry quote
lateness remains <=90 seconds.

Result: **NO_QUALIFIED_STRATEGY** under owner-selected strict improvement in
net profit, DD, realized RR and cost-stressed net. All candidates earned less
training net than baseline. Best candidate training net $173.49 versus $302.64;
DD 23.09% versus 42.54%; realized RR 2.172 versus 1.189; stress net $129.33 versus
$294.00. No candidate validation or promotion followed. Full baseline reproduced
$533.621 / 266 trades / DD 56.8941%. Costs, search bias, tests and evidence:
[logic tuning verdict](docs/reviews/2026-09-30-breakout-logic-tuning.md).

The all-metric improvement objective remains unmet. Demo orders and real money
remain NO-GO; existing frozen target and runtime configuration unchanged.
