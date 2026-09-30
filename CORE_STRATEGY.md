# Core Trading Strategy & Logic (Single Source of Truth)

**Last Updated:** 2026-09-29
**Status:** Research target (Pure B1 Single-Position); live execution NO-GO

เอกสารนี้คือ contract ของ Pure B1 ที่อยู่ระหว่างวิจัย ไม่ใช่คำยืนยันว่าทางเดิน live ใช้กติกานี้แล้ว **หากมีการเปลี่ยนแปลงเงื่อนไขการเทรดใดๆ Agent ทุกตัวต้องมาอัปเดตไฟล์นี้ทุกครั้ง**

---

## 1. ข้อมูลพื้นฐาน (Basic Info)
*   **Symbol:** XAUUSD (Gold); target Exness Demo ใช้ symbol ที่ terminal ยืนยัน (`XAUUSDm` ใน archived capture)
*   **Timeframe:** M15 (กราฟ 15 นาที)
*   **Capital Base:** $200 (Micro-account)
*   **Data/Execution target:** ใช้ Bid OHLC ของ UTC M15 ที่รวมจาก M1 ครบ 15/15 นาทีตาม archived replay. Shadow และ labeled replay ใช้กฎเวลาเดียวกัน `first_fresh_quote_age_60s_lateness_90s`: quote แรกหลังแท่งปิด, อายุไม่เกิน 60 วินาที และมาไม่เกิน 90 วินาทีหลังปิดแท่ง. BUY entry Ask / SELL entry Bid. Direct MT5 M15 อาจมีแท่งช่วงตลาดพักที่ reference ไม่รับ และห้ามป้อน detector. มี read-only Shadow entrypoint แต่ยังไม่มี broker fill หรือ live order path ของ Pure B1. หน้าต่าง 900 วินาทีของ replay เก่าเป็น scenario `archival_first_tick_within_900s` เท่านั้น.

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
    *   จำกัดการขาดทุนสะสมต่อวัน UTC ไม่เกิน 40% ของ day-start equity (เท่ากับ 40% พอดีให้ปฏิเสธ). Baseline คือ equity ที่บันทึกในวินาทีแรกของ 00:00 UTC พร้อม account fingerprint และ balance. ไฟล์ state ที่อ่านไม่ได้, คนละบัญชี, balance เปลี่ยน, หรือ equity ที่ต่ำกว่า balance โดยไม่มี snapshot ต้อง fail closed. ห้าม reset baseline จาก equity ปัจจุบัน. Labeled replay ไม่ใช้ `day_start.setdefault` ที่ signal tick และไม่ใช้ day quota 99. ถ้า position ลากข้ามเที่ยงคืนโดยไม่มี tick ในวินาทีแรก admission ถูกปฏิเสธ.
*   **Shadow broker gates:** ตรวจบัญชี Demo USD แบบ hedging, quote rule ด้านบน, symbol trade mode, stop/freeze distance, volume 0.01, margin และ broker profit calculation จาก snapshot. Position ที่ไม่มี symbol ต้อง fail closed. Cost policy เวอร์ชัน 1 อยู่ที่ `config/pure_b1_cost_policy.json`: Standard Demo, commission USD ต่อ 1 lot ต่อรอบเที่ยว, แหล่งอ้างอิงและวันที่ตรวจ, slippage เป็น declared assumption ไม่ใช่ค่าที่ terminal รับรอง. `symbol_info` ไม่ให้ commission tariff ก่อนส่งคำสั่ง; ถ้ายืนยันแหล่งไม่ได้ risk admission ปฏิเสธ. Bid/Ask รวม spread แล้ว จึงไม่บวก `spread_buffer`. Swap-free เป็นสถานะปัจจุบัน ไม่ใช่สิทธิ์ย้อนหลัง. ไม่มี `order_send` ใน Shadow. Per-bar parity ledger ณ 2026-09-29 ยัง BLOCKED จึงยังไม่ประกาศว่า Shadow ผ่าน.

## 5. ขอบเขตหลักฐานและการยืนยันผลลัพธ์ (Evidence)

กฎในเอกสารนี้เป็น **research target ที่เลือกศึกษา**; ยังไม่ใช่กลยุทธ์ที่ผ่านเกต Demo automation หรือเงินจริง. ผลย้อนหลังแต่ละชุดต้องระบุ signal, data source, fill/cost model และ risk admission; ห้ามนำผลคนละ contract มาเป็นผลของ target.

1. **ผล OHLC 2.7 ปี +700.4%:** งานคัดเลือกย้อนหลังใช้ public Dukascopy-derived Bid-only bars, entry ที่ signal-bar close และ flat USD 0.30 cost. ไม่มี Exness Bid/Ask fill, slippage, margin approval, swap-free history หรือ broker deal ledger จึงใช้เป็น research screening เท่านั้น. ตัวเลขนี้ไม่พิสูจน์ว่า EMA/RSI จำเป็นหรือทำกำไรได้ภายใต้บัญชีเป้าหมาย. ดู [broker conditions audit](docs/reviews/2026-09-29-xauusdm-broker-conditions-audit.md).
2. **ผล archived Exness tick +341.99%:** ใช้ RSI BUY ≤75 / SELL ≥25 และ **ไม่มี EMA50**; ไม่ใช่ signal contract ในเอกสารนี้. เป็น Python replay ไม่ใช่ order ที่ broker รับและ fill.
3. **ผล target บน Exness ticks ชุดเดียวกัน:** strict RSI 30–70 + EMA50 ได้ **-33.51%** ภายใต้ spread-only และ cost-inclusive 10% cap (4 trades). กรณีสมมติ fee 0.10R พร้อม current-spec swap ได้ **+150.31%** (49 trades) เพราะ fee เปลี่ยนการรับไม้และเส้นทาง equity; ไม่ใช่ค่าธรรมเนียม Standard ที่วัดจริง และไม่ใช่ผลที่คาดของ Standard Demo. ทั้งสองกรณียังไม่วัด broker slippage, margin approval และ historical swap entitlement. แหล่งตัวเลขและ hash ของ input/source: [target replay verdict](docs/reviews/2026-09-29-pure-b1-target-replay-verdict.md) กับ `data/b1_pure_target_replay_cost_gated_2026_09_29/contract.json`.
4. **Labeled replay 2026-09-29** บน input/contract ชุดเดียวกัน ด้วยกฎ quote 60s/90s, day-start ที่ไม่ reset เงียบ และไม่มี day quota 99: Standard/no-commission/swap-free-current-policy **-33.51% / 4 trades**; non-swap-free ได้ตัวเลขเดียวกันเพราะ 4 ไม้ไม่ข้ามเที่ยงคืน UTC และสิทธิ์ swap ย้อนหลังยังไม่มี; slippage/spread stress (declared 0.10 + 0.20, `spread_buffer` 0) **-33.608% / 4 trades**. ไม่ใช่ผล Demo ที่คาดไว้. รายละเอียด: [evidence pin](docs/reviews/2026-09-29-pure-b1-evidence-pin.md) และ [Demo verdict](docs/reviews/2026-09-29-pure-b1-demo-verdict.md).
5. **Parity ledger 2026-09-29:** canonical M15 เทียบ reference ใน overlap 1,812 แท่ง OHLC ตรง, แต่ risk decision ทั้ง 1,812 แท่งถูกบล็อกเพราะไม่มี cost snapshot ที่ตรวจแล้ว. Ledger gate คือ BLOCKED. Shadow ยังไม่ผ่าน. Direct M15 มี 27 แท่งที่ canonical 15/15 ไม่รับ.
6. **มติปัจจุบัน:** เลือก Donchian 30 + RSI 30–70 + EMA50, TP 6.25 ATR / SL 2.5 ATR, fixed 0.01 lot, 10% cap, daily 40% เป็น contract เป้าหมาย **เพื่อวิจัยต่อ**. Demo orders และเงินจริงเป็น NO-GO. `main.py` ยังรัน legacy wick strategy ไม่ใช่ Pure B1.
7. **ตัวเลือกจาก config search 2026-09-29:** บน tick Exness ชุดเดียวกัน โดยใช้สเปรด Bid/Ask และ commission 0 ตามเรท Standard ไม่ใส่ fee สมมติ Donchian 48 ที่ไม่มี RSI และไม่มี EMA50, SL 2.5 ATR, TP 3.0 ATR ได้ +166.81% ($533.62, 266 ไม้, DD 56.89%) และเป็นบวกทั้งสองครึ่งช่วง. Core ปัจจุบันบนรันเดียวกันยังเป็น -33.51%. ตัวเลือกนี้ยังไม่แทน contract ด้านบน และยัง NO-GO สำหรับออเดอร์. รายละเอียดอยู่ที่ [config search](docs/reviews/2026-09-29-exness-demo-config-search.md).

8. **Retrospective walk-forward tuning 2026-09-29:** ตรวจ raw capture 45,671,201 ticks ตรง tape และสร้าง canonical M15 12,100 แท่งกลับได้ตรง reference. Grid 15 ชุด (Donchian 40/48/56/64/72, TP 3.0/3.25/3.5, SL 2.5, RSI/EMA off) ยังไม่มีชุดผ่าน research DD ≤40% บน full window. Donchian 48/TP 3.5 ได้ +207.74%, DD 40.58%; 56/TP 3.5 ได้ +233.15%, DD 42.10%. Walk-forward เลือก 48/3.5 ในช่วงแรก ได้ +52.70% แต่ DD 43.79%; สองช่วงหลังไม่มี training candidate ผ่านเกณฑ์ จึงถือ cash. ทั้ง tape เคยใช้ค้นค่าแล้ว ไม่ใช่ untouched holdout; เกณฑ์ 40% เป็น research screen ไม่ใช่ risk tolerance สำหรับ live ที่เจ้าของอนุมัติ. **ยังไม่เปลี่ยน frozen contract หรือเปิด orders.** ดู [walk-forward tuning](docs/reviews/2026-09-29-exness-walk-forward-tuning.md).


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


### 6.1 Profit protection and entry-quality follow-up (2026-09-30)

Additional 48 research hypotheses (18 protection,30 entry quality),191 total
including earlier143. Break-even/candle-trail/runner activate only after a
closed bar shows >=0.5 initial risk in net executable profit; SL never widens.
BUY/SELL controls, candle body/close quality, and prior UTC calendar-day
direction tested. Prior-day guard uses bar-close date at midnight. All fixed
lot, cost-inclusive10% cap and daily40% admission controls retained.

Result remains **NO_QUALIFIED_STRATEGY**. Training SELL-only runner improves
net $330.00 versus baseline $302.64 and DD20.41% versus42.54%, but realized
RR0.832 versus1.189 and stressed net$290.12 versus$294.00 fail owner criteria.
No candidate validation or adoption. Full suite687 ran,685 passed,2 skipped.
Details and reproducible evidence: [follow-up](docs/reviews/2026-09-30-breakout-followup.md).


### 6.2 Central append-only strategy history (2026-09-30)

ประวัติกลาง: [Strategy Evolution / Change Log](docs/STRATEGY_EVOLUTION.md#central-strategy-change-log--2026-09-30).
บันทึกต่อท้ายด้วยID,from→trial,config snapshot,ช่วงข้อมูล,ผลbaseline/candidate,
และมติรับใช้. LOG-20260930-00แก้ข้อสรุปV3เก่า;LOG-01ถึง06เก็บการเปลี่ยนแปลง
และผลแต่ละรอบ. ข้อมูลเก่าคงไว้; correction/adoptionต้องเพิ่มรายการใหม่.
Research implementationหรือผลtrialไม่ได้หมายถึงเปลี่ยนcontractใช้งาน.
