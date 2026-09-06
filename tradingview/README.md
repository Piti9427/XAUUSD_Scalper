# 📊 TradingView XAUUSD Pro Copilot (Pine Script v6)

ชุดสคริปต์ **Pine Script v6** สำหรับวิเคราะห์และเทรดทองคำ (**XAUUSD / Gold**) โดยเฉพาะ พัฒนาต่อยอดจากระบบ EMA Crossover + Chandelier Exit เดิม ให้กลายเป็นระบบระดับสถาบันที่ปรับจูนสำหรับพฤติกรรมราคาทองคำบน Timeframe **M5 / M15**

---

## 📁 ไฟล์ที่มีให้เลือกใช้งาน

| ไฟล์ | ประเภท | เหมาะสำหรับ |
| :--- | :--- | :--- |
| [`xauusd_pro_copilot.pine`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_pro_copilot.pine) | **Strategy (ระบบทดสอบ Backtest)** | ทดสอบประสิทธิภาพ (Strategy Tester), ดู Win Rate / Profit Factor, จำลอง Spread Exness 30 pts ($0.30) และระบบปิดกำไรครึ่งหนึ่ง (Partial TP1) |
| [`xauusd_pro_indicator.pine`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_pro_indicator.pine) | **Indicator (อินดิเคเตอร์บนชาร์ต)** | แสดงผลบนชาร์ตแบบคลีน ไม่มีลูกศรคำสั่งซื้อขายกวนสายตา และรองรับเมนูสร้าง **Alertcondition** บน TradingView ได้โดยตรง |

---

## ⚡ คุณสมบัติเด่นที่อัปเกรดเพื่อทองคำ (Gold Upgrades)

1. **Bidirectional Trading (เทรดได้ทั้ง 2 ฝั่ง Long & Short):**
   - รองรับฝั่ง Short อย่างสมบูรณ์ (Bearish EMA Cross + Price < EMA 200 + Chandelier แดง)
2. **Dynamic ATR Risk Management (แทนที่ Fixed % SL/TP):**
   - ยกเลิก 5% SL / 15% TP เดิม (เพราะที่ทอง $2,500 5% คือ $125 หรือ 12,500 จุด ซึ่งไม่เหมาะกับการเดย์เทรด)
   - เปลี่ยนเป็น **Dynamic ATR / Pips**:
     - **SL:** คำนวณจาก ATR Multiplier (ค่าเริ่มต้น 1.5x ATR หรือ ~$3.00–$5.00)
     - **TP1 (Partial 50%):** 1.5 เท่าของระยะ Risk (R:R 1:1.5) เพื่อล็อคกำไรก้อนแรก
     - **TP2 (Runner):** 3.0 เท่าของระยะ Risk (R:R 1:3.0)
3. **Session Killzone Engine (London & New York):**
   - กรองสัญญาณเข้าเทรดเฉพาะช่วงที่มี Volume สูง ช่วยตัดสัญญาณหลอก (Whipsaw) ในช่วง Asian:
     - **London Killzone:** 07:00 – 10:00 UTC (14:00 – 17:00 เวลาไทย)
     - **New York Killzone:** 12:30 – 15:30 UTC (19:30 – 22:30 เวลาไทย)
   - มีแถบสีไฮไลท์พื้นหลังอัตโนมัติ (น้ำเงิน = London, ส้ม = NY)
4. **Asian Range Liquidity Box (00:00 – 07:00 UTC):**
   - ตีกรอบ High และ Low ของช่วงตลาดเอเชียอัตโนมัติ เพื่อให้เห็นจุดที่ราคามักจะวิ่งไปกวาดสภาพคล่อง (Liquidity Sweep) ก่อนกลับตัว
5. **Chandelier Exit Calibrated for Gold:**
   - ปรับ ATR Multiplier จากเดิม 3.0 ลงมาเหลือ **2.0** เพื่อให้กระชับและล็อคกำไรได้เร็วกว่า ไม่โดนลากคืนเวลาราคาทองสะบัดแรง
6. **Exness Spread Simulation:**
   - จำลอง Spread ของบัญชี Exness Standard (30 points / $0.30) ไว้ใน Backtester ทำให้ผลกำไรและ Drawdown สะท้อนสภาพตลาดจริง

---

## 🛠 วิธีติดตั้งบน TradingView

1. เปิดเว็บไซต์ [TradingView](https://www.tradingview.com) และเลือกคู่เงิน **`EXNESS:XAUUSD`** หรือ **`OANDA:XAUUSD`**
2. เลือก Timeframe เป็น **M15** (แนะนำสำหรับ Scalping/Day Trade ที่แม่นยำที่สุด) หรือ **M5**
3. ด้านล่างของหน้าจอ คลิกแถบ **"Pine Editor"**
4. ลบโค้ดเดิมออกทั้งหมด แล้ว Copy โค้ดจากไฟล์:
   - สำหรับ Backtest & Full Strategy: ก๊อปปี้โค้ดใน [`xauusd_pro_copilot.pine`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_pro_copilot.pine)
   - สำหรับใช้งานเป็น Indicator เฝ้าจอ: ก๊อปปี้โค้ดใน [`xauusd_pro_indicator.pine`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_pro_indicator.pine)
5. คลิกปุ่ม **"Save"** และคลิก **"Add to chart"** (เพิ่มลงในแผนภูมิ)

---

## 🔔 การตั้งค่า Alert และ Webhook (เชื่อมโยงบอท)

### กรณีใช้งาน Indicator (`xauusd_pro_indicator.pine`):
1. คลิกขวาที่กราฟ หรือคลิกที่ไอคอนนาฬิกาปลุก **"Create Alert"**
2. ในช่อง **Condition** ให้เลือก **`XAUUSD Copilot Ind`**
3. เลือกเหตุการณ์ที่ต้องการ:
   - `XAUUSD Buy Signal`
   - `XAUUSD Sell Signal`
   - `XAUUSD Exit Long`
   - `XAUUSD Exit Short`
4. ในช่อง **Trigger** ให้เลือก **`Once Per Bar Close`** (เพื่อป้องกัน Repaint)
5. ในช่อง **Webhook URL** (หากต้องการส่งเข้า Webhook / Telegram Bot):
   - กรอก URL Endpoint ของเซิร์ฟเวอร์ เช่น `http://YOUR_SERVER_IP:8000/webhook`

### Payload ตัวอย่าง (JSON Webhook Format):
```json
{
  "action": "BUY",
  "symbol": "XAUUSD",
  "price": 2515.50,
  "time": "2026-09-06T14:30:00Z",
  "note": "Bullish EMA 20/50 + CE Bullish + Killzone"
}
```

---

## ⚙️ คำแนะนำการปรับแต่งพารามิเตอร์ (Settings Recommendations)

- **Visual Mode:**
  - `Clean`: แสดงเฉพาะเส้น EMA 20, 50, 200 และลูกศรสัญญาณ เข้าใจง่าย เหมาะกับการดูกราฟเร็ว
  - `Balanced` (แนะนำ): แสดง Chandelier Exit Line (เขียว/แดง) และกรอบเป้าหมาย TP/SL ด้วย
  - `Full Debug`: แสดงจุดตัด Cross และทรานซิชันครบทุกมิติ
- **Risk Model:**
  - `Dynamic ATR` (แนะนำ): Stop Loss จะขยายตามความผันผวนของทองคำ ณ แท่งนั้นๆ โดยอัตโนมัติ
  - `Fixed Points ($)`: กำหนด SL เช่น $4.00 (400 จุด) และ TP1 $6.00 (600 จุด) แบบคงที่
