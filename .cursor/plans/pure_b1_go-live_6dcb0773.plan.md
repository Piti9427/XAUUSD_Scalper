---
name: Pure B1 broker-data parity and shadow
overview: ตรึง contract และข้อมูล Exness บัญชีเป้าหมายชุดเดียว ตรวจ replay parity แล้วทำ read-only Shadow; แผนนี้ไม่เปิด Demo order หรือเงินจริง
todos:
  - id: freeze-evidence
    content: ตรึง contract, reference data, cost policy และหลักฐานผล replay
    status: pending
  - id: broker-data-parity
    content: ดึง Exness M1/direct M15/Bid-Ask ticks แบบ read-only สร้าง canonical 15/15 M1 M15 แล้วเทียบ OHLC indicators signals และ risk decisions
    status: pending
  - id: decision-shadow
    content: ต่อ detector และ risk gate เดิมเข้าตัวตัดสินใจและ Wine shadow runner ที่ไม่มี order_send หรือ Telegram
    status: completed
  - id: verify-review
    content: เทสต์ end-to-end shadow seam, replay cost scenarios และออกมติ Demo แยก
    status: pending
isProject: false
---

# Pure B1: broker-data parity ก่อน Shadow

**ขอบเขต:** ทำ read-only capture, replay/decision parity และ Shadow เท่านั้น. แผนนี้ไม่อนุมัติ `order_send`, Demo strategy automation หรือเงินจริง. สถานะ Pure B1 ยังเป็น research target และ live execution NO-GO ตาม [CORE_STRATEGY.md](../../CORE_STRATEGY.md).

**ผล implementation รอบนี้:** [broker-bar parity audit](../../docs/reviews/2026-09-29-pure-b1-broker-bar-parity.md) บันทึก bounded MT5 capture, 15/15 M1 canonical bar parity, Shadow หนึ่งรอบแบบ no-signal และ replay recheck. `broker-data-parity` ยังไม่ครบเพราะไม่มี per-bar SL/TP/risk parity กับ account/cost snapshot ย้อนหลัง. `freeze-evidence` ยังไม่ผ่านเพราะยังไม่มี measured slippage/historical swap ledger หรือ cost policy ที่ตรวจสำหรับ session ปัจจุบัน; `verify-review` ยังไม่ผ่าน Demo/forward validation. `decision-shadow` completed เฉพาะ code + fake-MT5 tests เท่านั้น.

## Contract และแหล่งอ้างอิงเดียว

1. **กฎ:** [CORE_STRATEGY.md](../../CORE_STRATEGY.md) เป็นแหล่งเดียวของกฎเป้าหมาย: completed UTC Bid M15 **จาก M1 ครบ 15/15 นาที**, Donchian 30 ก่อนแท่งสัญญาณ, RSI14 EWM `30 < RSI < 70`, EMA50 EWM, ATR14 rolling mean, TP 6.25 ATR, SL 2.5 ATR, fixed 0.01 lot, 10% ของ current equity, daily 40%, ไม้เดียว, ไม่มี recovery. ตัวคำนวณจริงคือ `scripts/strategy.py:pure_b1_bars` / `pure_b1_levels` และ `scripts/smc/risk.py:check_fixed_lot_risk`. ถ้ากฎเปลี่ยน ต้องเปลี่ยน contract/version และ replay ใหม่. `main.py`, SMC webhook และ `mql5/B1FinalEA.mq5` เป็นคนละ runtime/contract; ห้ามนำผลหรือทางเดินนั้นมาแทน Pure B1.
2. **ข้อมูลและผลย้อนหลัง:** ยึด [target replay verdict](../../docs/reviews/2026-09-29-pure-b1-target-replay-verdict.md) และ `data/b1_pure_target_replay_cost_gated_2026_09_29/contract.json` ซึ่งบันทึก SHA-256 ของ source/input. Reference bars คือ `data/b1_hybrid_baseline_6mo_fixed_2026_09_28/reference_bars.csv`; Bid/Ask tick tape อยู่ใน `data/b1_hybrid_baseline_6mo_fixed_2026_09_28/tape/`; broker capture manifest คือ `data/b1_hybrid_exness_6mo_fixed_2026_09_28/manifest.json`. ทุกการเทียบต้องบันทึก account fingerprint, server, symbol (`XAUUSDm` ใน archive), UTC window, hashes, signal contract และ cost scenario; ห้ามเขียนทับ artifacts.
3. **ติดป้ายตัวเลข:** archive `+341.99%` ใช้ RSI 75/25 ไม่มี EMA50 จึงไม่ใช่ผล target. Target บน saved Exness ticks เดียวกันได้ `-33.51%` (spread-only, 4 trades) และ `+150.31%` (49 trades, สมมติ fee 0.10R + current-spec swap). Fee สมมติเปลี่ยนไม้ที่ผ่าน 10% cap จึงห้ามเรียกผลบวกว่า expected result ของ Standard Demo. ผล OHLC `+700.4%` ใช้ public Bid-only bars, flat cost และ entry ที่ signal-bar close; เป็น research screening ไม่ใช่ broker execution parity. อ้างผลและข้อจำกัดจาก verdict/manifest ข้างต้น ไม่ใช้ตัวเลขที่ไม่มี artifact.
4. **ต้นทุนบัญชี:** [broker conditions audit](../../docs/reviews/2026-09-29-xauusdm-broker-conditions-audit.md) ระบุ Exness Standard Demo, commission tariff ปัจจุบันเป็นศูนย์ และ Personal Area แสดง swap-free qualified ณ วันตรวจ. Swap-free อาจเปลี่ยน; `symbol_info` ไม่ให้ commission tariff ก่อนส่งคำสั่ง. เก็บ cost policy แบบ versioned พร้อม account type/แหล่งอ้างอิง/วันที่ตรวจ และหน่วยของค่า commission (USD ต่อ 1 lot, ต่อข้างหรือรอบเที่ยว); ถ้ายืนยันไม่ได้ risk decision ต้องปฏิเสธ. `history_deals_get` ใช้ตรวจ commission, fee, swap และ fill จริงหลัง Demo execution ที่ได้รับอนุมัติแยก. Slippage allowance เป็น assumption ที่ประกาศและ stress test ไม่ใช่ค่าที่ terminal รับรอง. Bid/Ask entry รวม spread แล้ว ห้ามบวก `spread_buffer` ซ้ำ.

## ลำดับงานและหลักฐานรับงาน

### 1. Read-only broker capture และ parity

- ใช้ Wine MT5 terminal ของ Demo login/server/symbol เป้าหมายเดียวกัน ตรวจ `account_info`, `symbol_info`, `symbol_info_tick`. ดึง Bid M1 ด้วย `copy_rates_range(..., TIMEFRAME_M1, ...)`, direct M15 เพื่อวินิจฉัย และ Bid/Ask ticks ด้วย `copy_ticks_range(..., COPY_TICKS_ALL)`; สร้าง canonical M15 จาก M1 ที่ครบ 15/15 นาที. `scripts/pure_b1/capture.py` เก็บ manifest/hash แบบ read-only. API จำกัดด้วย available chart history/Max bars in chart. Direct M15 ที่มี M1 ไม่ครบห้ามป้อน detector แม้แท่งปิดแล้ว.
- แปลง Unix seconds เป็น timezone-aware UTC; ตัด forming M1 และ M15 แล้วสร้าง `DatetimeIndex` ก่อนเรียก `pure_b1_bars`. `rates_to_frame` / `drop_forming_bars` คืน `RangeIndex`; ส่งตรงจะ `ValueError`. ตรวจลำดับ, duplicate, alignment, M1 ครบ 15/15, terminal clock และ quote age. กำหนดเวลารับ first fresh quote หลัง bar close ให้ชัด แล้ว replay ด้วยกฎเวลาเดียวกัน; แท่งขาด/เก่า/มาช้าให้บันทึกเหตุและไม่สร้าง late entry.
- เปรียบเทียบ broker M15 OHLC กับ M15 ที่รวมจาก ticks และ `reference_bars.csv` เฉพาะ window ที่ซ้อนกัน; บันทึกทุก mismatch พร้อมขนาด/สาเหตุ. เทียบ RSI/EMA/ATR, signal timestamp/direction, SL/TP และ risk decision ทีละแท่ง. EWM ขึ้นกับประวัติตั้งต้น: กำหนด warmup หรือ persist indicator state ให้ parity กับ replay; ห้ามถือว่า 100/500 แท่งพอโดยไม่มีผลเทียบ. หาก data/contract ไม่ตรง ให้แก้สาเหตุและ replay ใหม่ก่อนผ่านขั้นนี้.

### 2. Pure decision และ Shadow

- เพิ่มโมดูลตัดสินใจที่รับ completed UTC M15 bars, fresh Bid/Ask, account/symbol snapshot, verified cost policy, position/pending snapshot และ day-start state; คืน admit/reject พร้อมเหตุผล. เรียก detector/risk function เดิม ไม่เขียน RSI/EMA/Donchian หรือ risk formula อีกชุด. BUY เข้า Ask / SELL เข้า Bid; ปัด SL/TP ตาม tick size แล้วตรวจความเสี่ยงอีกครั้ง. Fixed 0.01 lot ต้องตรง broker min/max/step; เกิน 10% ของ current equity ให้ reject ไม่ลด/เพิ่ม lot. ข้อมูลหรือ cost/slippage model ขาดให้ fail closed.
- Single-position: มี **position หรือ pending order ใด ๆ** บน symbol เป้าหมายให้ไม่รับไม้ใหม่; comment/magic ใช้ระบุ ownership สำหรับ reconcile เท่านั้น และห้ามแก้/ปิดของระบบอื่น. ตรวจ quote freshness, market/session availability, volume, stops/freeze, equity และ `order_calc_margin` / `order_calc_profit` บนบัญชีเดียวกันเพื่อประเมิน margin/HMR ใน Shadow; สิ่งที่ read-only ตรวจไม่ได้ต้องระบุ unverified.
- Daily 40%: บันทึก equity ณ จุดเริ่มวัน UTC ที่นิยามชัด, account fingerprint และ watermark ข้าม restart. ถ้าข้อมูลหาย/อ่านไม่ได้ หรือ deposit/withdrawal, foreign PnL, floating-loss ทำให้ตัดสินไม่ได้ ให้ fail closed และบันทึกเหตุ; ห้าม reset baseline จาก equity ปัจจุบันโดยเงียบ ๆ. แยก daily account-equity guard จาก per-trade 10% gate.
- Wine shadow runner อ่าน terminal แบบ read-only, dedupe หนึ่ง decision ต่อ completed bar, เขียน JSONL แบบ append-only รวม contract/data/cost-policy hash, bar UTC, Bid/Ask และ quote age, indicator/ATR, SL/TP, equity, broker specs, exposure, spread, cost assumptions, result/reason และ `order_api_called:false`. ไม่เรียก `order_send`, ไม่เปิด SMC send flag, ไม่ส่ง Telegram. Identity/clock/data/cost policy ผิดหรือขาดให้ fail closed.

### 3. Verification และมติถัดไป

- Test seam fake MT5 rates/ticks → UTC/index adapter → detector → risk/daily/exposure decision → JSONL. ครอบคลุม forming bar, warmup parity, duplicate/gap/stale quote, restart state, account mismatch, foreign/pending exposure, exact 10%/40% boundary, missing/zero-with-source commission, slippage, tick rounding และนับ `order_send=0` / Telegram=0. รัน `.venv/bin/python -m unittest discover -s tests` หรือ `make test` ตาม environment; ตรวจ diff และเก็บผล. Focused tests ไม่ใช่ broker parity.
- Replay ใหม่ด้วย input/contract ที่ hash ตรึงไว้ แยก Standard/no-commission/swap-free-current-policy, non-swap-free และ slippage/spread stress. ข้อมูล swap entitlement ย้อนหลังและ broker fills ยังขาด; ห้ามใช้ค่าปัจจุบันย้อนหลังโดยไม่ติดป้าย scenario. ก่อนประกาศ Shadow ผ่าน ต้องแสดง per-bar parity ledger และอธิบาย mismatch ทุกจุด. อัปเดต [CORE_STRATEGY.md](../../CORE_STRATEGY.md) เฉพาะ implementation/evidence ที่เกิดจริง.
- **Demo execution probe:** ต้องมี proposal/approval แยกหลัง data parity และ risk tests ผ่าน. Probe พิสูจน์ adapter/fills ไม่ qualify กลยุทธ์. ส่ง notification หลัง broker ยืนยัน fill จาก retcode/deal/position reconciliation ไม่ใช่เพียง ticket; เก็บ requested/filled price, latency, rejection, commission, swap, margin และ SL/TP behavior จาก `history_deals_get`.
- **Demo strategy automation:** ต้องผ่านเกณฑ์ที่ preregister สำหรับ Pure B1 บน Exness Bid/Ask **หลัง freeze**, measured costs และ statistical/risk gates ตาม [ADR-0030](../../docs/adr/0030-bottradegold-independent-qualification.md). [ADR-0025](../../docs/adr/0025-profitability-qualification.md) เป็นของ Pine Master Pro; ตัวเลข 12 สัปดาห์/100 trades/90% fidelity ใช้กับ Pure B1 ได้เมื่อปรับและบันทึกเป็น contract เฉพาะ. หนึ่ง Shadow bar หรือ Demo probe ไม่ qualify กลยุทธ์.
- **เงินจริง:** NO-GO จนมี forward Demo evidence, broker cost/fill reconciliation, zero risk breach, owner review และอนุมัติแยก. แผนนี้ไม่ตั้ง `XAUUSD_REAL_MONEY_APPROVED` หรือ `real_money.approved`, ไม่แก้ `main.py` ให้เทรด, ไม่ปลด tester gate ของ EA.
