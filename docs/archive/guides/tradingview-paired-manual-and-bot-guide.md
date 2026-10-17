# คู่มือใช้ XAUUSD Master Pro แบบคู่

ไฟล์สองตัวมีหน้าที่ต่างกัน:

- `xauusd_master_pro_v6.pine` — Indicator สำหรับอ่านกราฟ, setup, Entry, SL, TP1, TP2 และ manual alerts
- `xauusd_master_pro_strategy.pine` — Strategy สำหรับ Strategy Tester และตรวจว่ากฎเดียวกันให้ผลย้อนหลังอย่างไร

ยังไม่ควรเปิด bot ส่ง Demo order จนกว่า broker lifecycle worker, execution policy, runtime news gate และ Demo canary ตาม remediation plan จะผ่านครบ

## ตั้งค่ากราฟ

1. เปิด `EXNESS:XAUUSD` หรือ symbol เดียวกับบัญชี MT5
2. ใช้ timeframe `15m`
3. เพิ่ม Indicator และ Strategy ลงกราฟเดียวกัน
4. ตั้งค่าทั้งสองตัวให้ตรงกัน:
   - `Trade Direction`: `Both`
   - `Signal Engine Mode`: `Confluence (2+)`
   - `Visual Preset Mode`: `Balanced (Clean)`
   - `Await Bar Confirmation`: เปิด
   - Session filter: เปิด
   - Rollover block: `20:45-23:00 UTC`
   - `Max SL Cap`: `$25`
   - `TP1`: `1.0R`
   - `TP2`: `2.5R`
5. ใน Indicator ตั้ง `Alert Output = Manual Card` สำหรับเทรดเอง

## อ่าน setup ก่อนเข้าออเดอร์เอง

รับ setup เฉพาะเมื่อแท่งปิดและรายการนี้ตรงกัน:

- Indicator แสดง `LIMIT BUY`, `LIMIT SELL`, `BUY FILLED` หรือ `SELL FILLED`
- Strategy แสดง `BUY` หรือ `SELL` บนแท่งเดียวกัน
- `Engine`, session และ `H1 Bias` ใน HUD สนับสนุนทิศทางเดียวกัน
- Entry, SL, TP1 และ TP2 ของสองตัวตรงกัน
- ไม่อยู่ `ROLLOVER BLOCK`
- ข่าว USD impact สูงอยู่นอกช่วงห้ามเทรดตาม runtime calendar
- คำนวณ lot จาก equity/balance และข้อกำหนด broker; ห้ามใช้ข้อความ `Risk: $` จาก Indicator เป็น lot sizing

หากสอง Pine ไม่ตรงกัน ให้ข้าม setup และบันทึกเวลา UTC, symbol, timeframe, parameter และภาพกราฟไว้ตรวจ parity

## จัดการไม้แบบ manual

- SMC ใช้ limit entry; ยกเลิกเมื่อ TTL หมดหรือ killzone จบ
- TSS/GSS เป็น model entry ที่ราคาปิดแท่งยืนยัน; ตรวจราคาจริงก่อนส่ง market order
- วาง SL พร้อม order เสมอ
- เมื่อถึง TP1: ปิด 50% แล้วเลื่อน SL ส่วนที่เหลือไป breakeven พร้อม buffer ที่ตั้งไว้
- TP2 ปิด runner
- ปิดสถานะก่อน cutoff `20:45 UTC` บน M15
- Telegram หรือ TradingView card คือคำแนะนำจาก model; broker ticket คือหลักฐานว่า order ถูกยอมรับจริง

## Alerts

สร้าง TradingView alert โดยเลือก condition `Any alert() function call`:

- `Manual Card` — อ่านง่ายสำหรับเทรดเอง
- `Bot JSON` — JSON ล้วนสำหรับ webhook; ห้ามส่งไป execution bridge จน Demo remediation gates ผ่าน
- `Off` — ปิด dynamic alerts แต่ยังดูกราฟได้

อย่าใช้ Indicator และ Strategy ส่ง execution webhook พร้อมกัน เพราะ setup เดียวอาจถูกส่งซ้ำจากคนละ source

## ตรวจ Strategy Tester

Strategy Tester ใช้ตรวจ candidate logic และเทียบ setup ไม่ใช่คำรับรองกำไร:

1. ใช้ symbol, timeframe, date range, commission และ slippage ตรงกับการใช้งานจริง
2. ตรวจอย่างน้อย 100 trades และแยก long/short, London/New York
3. ต้องผ่าน PF, expectancy, drawdown, cost stress และ bootstrap gates ใน `docs/adr/0025-profitability-qualification.md`
4. จากนั้น forward Demo อย่างน้อย 12 สัปดาห์และ 100 trades

## หลักฐานก่อนเปิด auto order

- Pine compile ผ่านทั้งสองไฟล์
- Side-by-side parity ผ่านบน historical และ realtime bars
- Webhook payload ผ่าน contract test
- Bridge ยืนยันบัญชี Exness Demo และ symbol policy
- Broker lifecycle worker จัดการ fill, TP1, BE, cancel, close และ restart reconciliation
- Risk/news/circuit-breaker gates fail closed
- Demo canary ผ่านโดยไม่มี risk breach หรือ phantom alert

ภาพ flow: [paired trading workflow](../diagrams/xauusd-paired-trading-workflow.html)

