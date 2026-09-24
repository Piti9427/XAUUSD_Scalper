# ปรับ Master Pine ให้ทดสอบกำไรสุทธิได้ตรงกับการใช้งาน

> วันที่: 2026-09-12
> สถานะ: แผนที่ตกลงในบทสนทนา — ยังไม่ได้ implement ตามแผนนี้
> Primary artifact: [xauusd_master_pro_v6.pine](../../tradingview/xauusd_master_pro_v6.pine)
> Review ต้นทาง: [Master Pro v6 logic review](../reviews/2026-09-12-master-pro-v6-logic-review.md)

## 1. เป้าหมายและข้อตกลง

ปรับ `tradingview/xauusd_master_pro_v6.pine` เป็น **strategy ตัวเดียว** สำหรับกราฟ, HUD, alerts และ Backtest คุณส่งคำสั่งจริงเอง

- เป้าหมาย: **net expectancy ดีขึ้นภายใต้ drawdown จำกัด** ไม่บังคับเพิ่ม win rate
- บัญชีอ้างอิง: Exness Standard Demo, USD500; M15 หลัก, M5 รายงานแยก
- Risk ต่อไม้0.5%; daily stop เมื่อขาดทุนสุทธิ2ไม้หรือ equity ลด1%; drawdown5% หยุดรับ setup
- คง SMC/TSS/GSS เพื่อเปรียบเทียบ ไม่เพิ่ม indicator/filter หรือค้นพารามิเตอร์จำนวนมากรอบแรก
- แยกสถานะ **software verified**, **backtest evaluated**, **forward verified**; ห้ามใช้แทนกัน

## 2. แก้ detection และ setup ให้ถูกต้อง

- แก้ Pine API incompatibilities ทั้ง plotting, timestamp และ JSON formatting
- H1/PDH/PDL ใช้ข้อมูลแท่งก่อนหน้าที่ปิดแล้ว พร้อม HTF merge แบบ `[1] + lookahead_on`; รับเฉพาะกราฟแท่งเวลาปกติ M5/M15
- SMC ผูก sweep → MSS → FVG เป็น setup เดียว: freeze extrema เมื่อยืนยัน MSS, ไม่ยืม extrema จาก sweep ใหม่ และไม่ใช้ setup เดิมเข้าอีกรอบ
- MSS ภายใน8แท่งหลัง sweep; FVG ใช้ MSS หรือแท่งถัดไปไม่เกิน4แท่งเป็น **middle candle** ต้องรอ right-hand candle ปิดก่อนวาง limit50%
- Sweep ใหม่แทน setup ที่ยังไม่ส่งคำสั่ง; สำหรับ pending ยกเลิกเมื่อเกิด opposite sweep หรือเงื่อนไข validity เสีย ก่อนเริ่มค้น setup ใหม่
- GSS freeze คู่ swing ตามลำดับจริง และกำหนดให้ impulse มี displacement ตามนิยามเดิม45%; ไม่เพิ่ม ATR threshold รอบนี้
- SMT เปรียบเทียบ swing XAU กับ DXY ที่ตรงช่วงเวลา โดยไม่นับค่าปัจจุบันรวมใน reference extrema; ข้อมูลไม่ครบแสดง unavailable ใช้เป็นข้อมูลประกอบเท่านั้น
- คงค่าระยะและ R เดิมเป็น baseline; แก้ชื่อหรือข้อความที่อ้างความแม่นยำเกินสิ่งที่ตรวจจริง

## 3. Execution simulation, risk และ alerts

**ใช้ native strategy orders เป็นแหล่งสถานะจำลอง** เลิกนับ fill/TP/SL จากการแตะ High/Low ด้วย state machine แยกอีกชุด

- ตรวจ setup เมื่อแท่งปิด; TSS/GSS ส่ง market order สำหรับ tick ถัดไป ส่วน SMC วาง limit หลังยืนยัน FVG ห้ามนำราคาก่อนส่งคำสั่งมาคิดผล
- เตรียม protective SL/TP พร้อม entry; หลัง fill ใช้ราคาที่ emulator ยืนยัน บันทึก gap/slippage และ risk ที่เกินแผนตามจริง ไม่ลบ trade ย้อนหลัง
- การคำนวณซ้ำหลัง fill ทำเฉพาะ lifecycle/exit management ห้ามใช้ข้อมูลปลายแท่งเปิด setup ใหม่ระหว่าง fill callback
- Lot ปัดลงตาม broker step และ budget รวมต้นทุนประมาณการ; ต่ำกว่า minimum ให้ข้าม ห้ามเพิ่ม lot หรือบีบ structural SL
- ถ้าแบ่งได้ ให้ใช้สองส่วนเท่ากันที่ตรง lot step: 50% TP1=1R และ runner TP2=2.5R; เลื่อน BE หลังยืนยัน partial fill เท่านั้น
- ถ้าเปิดได้เพียง0.01 lot ให้ปิดเต็มที่TP1 ไม่มี partial/runner; รายงาน expectancy แยกตาม exit mode
- Pending มีอายุ4แท่งถัดจากแท่งสร้างคำสั่ง ยกเลิกเมื่อครบ TTL, หมด killzone, H1 เปลี่ยนฝั่ง, structural invalidation, news blackout หรือ risk halt; fill ที่เกิดก่อน cancellation ต้องถูกบันทึก
- ใช้ session UTC เดิม; สำหรับ deadline20:55 ให้ปิดจำลองที่20:45บนM15 และ20:50บนM5 ซึ่งเป็นจุดปิดแท่งก่อน deadline พร้อมระบุเวลานี้ใน HUD/alert
- Daily/DD guards อิง **พอร์ตจำลองของ strategy**; ไม่อ้างว่ารวม manual trades หรือควบคุมบัญชีจริงได้
- รับรายการเวลา USD HIGH แบบ UTC พร้อมช่วงวันที่ coverage; บล็อก setup/pending ±30นาที Position ที่เปิดแล้วคง SL/TP ตาม lifecycle ปกติ
- รายการข่าวผิดรูปแบบหรืออยู่นอก coverage ให้หยุดรับ setup และแสดงเหตุผล

**Alert interface เปลี่ยนเป็น version2:** JSON object เดียว มีข้อความอ่านง่าย, setup/trade ID, symbol, timeframe, event time และ `simulation=true` ทุกข้อความ สถานะ fill ใช้คำว่า `SIMULATED_FILL`; cancellation/expiry มี event ชัดเจน ผู้ใช้ต้องสร้าง alerts ใหม่

## 4. ตรวจ correctness ก่อนเลือกกลยุทธ์

**Software gate**

- สร้าง regression จาก7 counterexamples เดิมก่อนแก้ พร้อม BUY/SELL: pre-entry TP, SL/TPชนแท่งเดียว, fillแล้วstop, BEย้อนหลัง, SMT, cross-sweep SL และ rollover
- เพิ่ม cases สำหรับ TTL boundary, session/news cancellation, min lot, partial lot step, daily reset, risk halt และ alert order/duplicate
- รัน Python suite เดิม; ตรวจ Pine compile และ runtime บน TradingView จริง แยกหลักฐานออกจาก Python transcription
- ตรวจ H1/day boundaries และ reload consistency; ใช้ Bar Magnifier เมื่อมีข้อมูล พร้อมเปิดเผยช่วงที่ไม่มี intrabar coverage ตามข้อจำกัดของ [TradingView](https://www.tradingview.com/support/solutions/43000669285-what-is-bar-magnifier-backtesting-mode/)

**Profitability gate**

- Comparator คือ Master ที่แก้ correctness แล้วด้วยค่าเดิม ไม่ใช้ผลจากรุ่นที่จำลองผิด
- เปรียบเทียบเพียง4โหมด: SMC, TSS, GSS และ combined dispatcher; ยังไม่เพิ่ม parameter sweep
- ใช้ Spot XAUUSD จาก feed ที่ระบุชัด พร้อม broker volume specification และต้นทุน; `GC=F` ใช้เป็นหลักฐาน Exness ไม่ได้
- ข้อมูลที่เคยตรวจหรือใช้ปรับค่าทั้งหมดเป็น development; ใช้ June–July2026 เลือกโหมด และ August1–September11,2026 เป็น holdout ที่ห้ามใช้ปรับค่า หากเคยเปิดดูเพื่อปรับแล้ว ให้ยกเลิกสถานะ holdout และใช้ข้อมูลใหม่
- ก่อนทดสอบ freeze dataset, code hash, news coverage และต้นทุน baseline; ทดสอบ stress โดยเพิ่ม spread/slippageเป็น2เท่า ไม่สมมติว่าต้นทุนเป็นศูนย์
- นับหนึ่ง position lifecycle เป็นหนึ่ง trade รวม partial exits ก่อนคำนวณ net R, win/loss/flat, PF, drawdown และ losing streak
- เลือก candidate ที่ net expectancy สูงสุดใน validation ภายใต้ risk limits; ผลเสมอใช้ drawdownต่ำกว่า แล้วเลือก engineเดี่ยวก่อน combined
- Holdout ต้อง net expectancyเป็นบวก, PF>1, drawdownไม่เกิน5% และ expectancyดีกว่า comparator; ใช้ paired weekly-block bootstrap10,000รอบตรวจ lower95% bounds ของ expectancy และผลต่าง หากหลักฐานไม่พอรายงาน **INCONCLUSIVE**
- Forward Demo12สัปดาห์หลัง freeze: เทียบ simulated alerts กับคำสั่งที่คุณเทรดจริง แยกผลสองชุด ไม่ปรับค่ากลางรอบ

## 5. เอกสารและเกณฑ์ส่งมอบ

- ปรับ `CONTEXT.md` ให้คำว่า Setup, Simulated Fill, Executed Fill, Risk Budget และ Net Winning Trade ไม่ปะปนกัน เก็บประวัติข้อตกลงเดิมและระบุข้อที่ถูกแทนที่
- อัปเดตคู่มือการตั้ง strategy properties, cost/lot calibration, ข่าว, alerts และข้อจำกัดการจำลอง
- อัปเดต review verdict พร้อม code hash, commands, compile evidence และผลการประเมิน
- หากยังขาด TradingView access, feed, ต้นทุน หรือข่าวย้อนหลัง ให้ส่งมอบโค้ดพร้อมระบุ verification ที่ยังไม่ครบ ห้ามประกาศว่ากำไรดีขึ้นแล้ว

**ขอบเขตรอบนี้:** ปรับ Pine และเครื่องมือตรวจที่จำเป็น ไม่มี auto-trading, deployment หรือการเปิดคำสั่งเงินจริง
