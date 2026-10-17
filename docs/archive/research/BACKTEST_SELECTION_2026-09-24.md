# ผลคัดเลือก backtest — 2026-09-24

คำตัดสินล่าสุด: [FINAL_CANDIDATE.md](FINAL_CANDIDATE.md) ล็อก `Donchian20_H4 / common` เป็นตัวเดียวสำหรับพัฒนาและ validation ต่อ ตาราง shortlist ด้านล่างเก็บเป็นหลักฐานการเปรียบเทียบ

เลือก **Donchian20_H4 / common** เป็นตัวหลักสำหรับพัฒนาต่อจากกำไรรวมย้อนหลังสูงสุดในชุดที่ทดสอบ ผลนี้เป็นการเสนอ research candidate; ยังไม่ผ่านการรับรอง Demo automation หรือเงินจริง

## ขอบเขตและวิธีคัด

- รวม 129 strategy identifiers: 120 specs เดิม, RSI cross-back ใหม่, top-down 3 policies และ handoff parameter variants 5 ตัว เมื่อแยก common/native ตามที่แต่ละ runner รองรับ ได้ 250 configurations ชื่อบางตัวเป็น alias หรือมีสัญญาณสัมพันธ์กัน จึงไม่ใช่การค้นพบอิสระ 250 ครั้ง
- อันดับรวมใช้ปีเต็ม **2011–2025** เพราะ top-down ต้องใช้ปี 2010 อุ่น indicator รายงาน 2010–2025 ของชุดเดิมยังเก็บไว้ตรวจความไวต่อช่วงข้อมูล
- รัน baseline 120 specs, top-down 3 policies และ handoff 5 variants ใหม่ด้วยโค้ดปัจจุบัน; ใช้ RSI run ที่ตรวจ code/input hashes ตรงกัน ช่วงที่ใช้คิดกำไรเหมือนกัน แต่ warmup เป็นไปตาม contract ของแต่ละ strategy
- ใช้ Bid/Ask M1 OHLC จาก revision `922f83a60cc574e7395fb27397077288055a1ef6` ของแหล่ง Dukascopy-derived เดิม มี source flat minutes ตามที่บันทึกใน data audit ข้อมูลนี้ไม่ใช่ real ticks ของ Exness
- คัดกำไรรวมไม่เป็นบวกออก; พักตัวที่ต่ำกว่า 200 trades หรือกำไรไม่ถึงครึ่งของปี; เรียงตัวที่เหลือตาม net ลดหลั่น เกณฑ์จำนวน trades/สัดส่วนปีอ้างอิง exploratory screen เดิม นี่เป็น shortlist แบบย้อนหลัง ไม่ใช่เกต `REVIEW_CANDIDATE` หรือ prospective qualification
- ตัวเลขคำนวณจาก trade logs: win rate = trades ที่ net > 0 / closed trades ทั้งหมด หนึ่ง trade คือหนึ่ง position เปิด–ปิดใน simulation ไม่ใช่จำนวนคำสั่งหรือ fills จริงของโบรกเกอร์
- แต่ละ configuration ทดสอบแยกกัน ไม่ได้นำกำไรหลายกลยุทธ์บวกเป็นผล portfolio

## ตัวที่เหลือสำหรับวิจัยต่อ

หน่วยกำไร **USD ต่อ fixed 1 oz-equivalent exposure** รวม historical Bid/Ask spread; commission, slippage, swap เพิ่มเติมยังเป็นศูนย์ที่ไม่ผ่านการวัดจาก Exness ไม่ใช่ผลตอบแทนของบัญชีทุนจริง

| Strategy | Mode | กำไร | Trades | Win rate | PF | ปีที่กำไร |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| **Donchian20_H4** | **common** | **1,066.74** | **1,305** | **35.17%** | **1.090** | **8/15** |
| Donchian20_H4 | native | 644.51 | 1,281 | 34.43% | 1.055 | 8/15 |
| AsianRetest__h1ema | native | 290.79 | 1,064 | 34.21% | 1.099 | 8/15 |
| ATR1.5__h1structure | native | 256.29 | 1,835 | 32.37% | 1.046 | 8/15 |
| AsianBreak__h1structure | native | 63.84 | 997 | 31.80% | 1.024 | 8/15 |
| ATR1.5_H4 | native | 43.82 | 634 | 35.17% | 1.007 | 9/15 |
| AsianRetest__fvg | common | 22.36 | 575 | 32.35% | 1.014 | 8/15 |

รวม **223 configurations คัดออกเพราะ net <= 0**, **20 พัก** (8 sample น้อย, 12 ปีที่กำไรไม่ถึงครึ่ง), **7 อยู่ใน shortlist**. รายการ CSV มีทุกตัวรวมที่คัดออกด้วย

`ATR1.5_H4 / common` มีกำไร 611.02 แต่ปีที่กำไร 7/15 จึงพักตามเกณฑ์; top-down dual-entry และ strict กำไร 267.13 และ 227.48 แต่กำไรเพียง 6/15 ปี จึงพักทั้งคู่ ส่วน context-any ขาดทุน และ RSI cross-back ถูกคัดออก

## Contract ที่เลือกและข้อจำกัด

`Donchian20_H4 / common`: ใช้แท่ง H4 Bid ที่ปิดครบ; close ทะลุ high/low ของ 20 แท่งก่อนหน้าจึงส่งสัญญาณตามทิศ; เข้า exact next M1 open; SL = 2 × H4 ATR14, TP = 2R; หนึ่ง position ต่อครั้งและเข้าได้ทุก regime. ใช้กฎ stop-gap และ stop-first ใน M1 ที่กำกวมตาม engine เดิม `native` ต่างตรงงดเข้า sideway จึงห้ามนำผล common ไปอ้างว่าเป็นผลของ native

- ช่วงร่วม 2011–2025: net 1,066.74; 1,305 trades (ชนะ 459, แพ้ 846); win rate 35.17%; PF 1.090; เฉลี่ย 0.8174 USD/oz/trade; maximum ของ marked-equity DD รายปี 417.68 USD/oz ซึ่งไม่ใช่ continuous account DD เป็นเปอร์เซ็นต์
- เพิ่มปี 2010 กลับเข้าไปเป็น 2010–2025: net **833.23**, 1,385 trades, win rate **34.66%**, PF **1.067**, ปีที่กำไร 8/16 อันดับกำไรรวมของชุดเดิมยังสูงสุด
- ปี 2024 และ 2025 ให้กำไรรวม 1,318.64 ขณะที่ปี 2011–2023 รวม **-251.90**. ผลจึงพึ่งช่วงหลังมาก
- ฝั่ง long ปี 2011–2025 = **+1,875.77**; short = **-809.03**. ยังไม่ได้เลือก long-only เพราะนั่นคืออีก contract ที่ต้องทดสอบแยก
- Diagnostic ช่วง 2025–2026 ถึง 20 ส.ค.: net **1,594.99**, 151 trades, win rate **45.70%**, PF **1.367**. ช่วงนี้ซ้อนกับปี 2025 ที่ใช้จัดอันดับและเป็นข้อมูลที่เคยเห็นแล้ว ไม่ใช่ untouched OOS

จึงเลือกเป็น **ตัวแรกที่จะพัฒนาทดสอบต่อ** จากกำไรย้อนหลัง แต่หลักฐานยังอ่อนสำหรับเงินจริง โดยเฉพาะต้นทุนที่ยังไม่วัด, ผลฝั่ง short, ความกระจุกตัวของกำไร และการจัดอันดับจากหลาย configurations

การเลือก common เป็นข้อเสนอ policy ใหม่สำหรับ prospective validation ไม่ได้แก้รายชื่อ/เกตที่ freeze ไว้ใน `QUALIFICATION_PROTOCOL.md`. ก่อนนำไปทดสอบเพื่อขอ qualification ต้อง freeze contract นี้และปรับจำนวนการทดสอบใน statistical correction ให้ตรงชุดจริง แล้วเก็บ Exness Demo ticks/costs, จำลอง lot ที่เสี่ยงไม่เกิน 0.5%, account DD และ twice-cost replay ตาม protocol

## หลักฐานที่เปิดตรวจได้

- [ทุก 250 configurations จัดอันดับ](../../data/research_results/selection-129-20260924/all-250-configurations-2011-2025-ranked.csv)
- [shortlist พร้อมกำไร/จำนวน trades/win rate/DD](../../data/research_results/selection-129-20260924/shortlist.csv)
- [ผลรายปีของตัวที่เลือก](../../data/research_results/selection-129-20260924/winner-annual.csv)
- [manifest และ hashes ของ source runs/output](../../data/research_results/selection-129-20260924/manifest.json)
- [baseline ใหม่ 2010–2025](../../data/research_results/selection-baseline-2010-2025-20260924/summary.csv)
- [สคริปต์รวมผลและตรวจ reconciliation](../../data/research_results/build_selection.py)

ตรวจ COMPLETE, source/code hashes, trade chronology, net, PF และ win rate จาก trade logs ก่อนสร้างอันดับ ไม่มีการเปลี่ยน strategy production code ในรอบคัดเลือกนี้; ผลและ script รวมผลอยู่ใน generated directory ที่ Git ignore ไว้ เก็บทั้ง directory เมื่อย้ายหรือสำรองหลักฐาน
