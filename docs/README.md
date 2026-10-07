# เอกสารที่ใช้กับบอทตอนนี้

บอท Demo ที่รันอยู่คือ C22 + H4 EMA200. อ่านสี่ไฟล์นี้พอ.

| เรื่อง | ไฟล์ |
|---|---|
| สัญญาและตัวเลขที่ล็อก | [`../CORE_STRATEGY.md`](../CORE_STRATEGY.md) หัวข้อ 6.33 |
| วิธีรันและหยุดบน Demo | [`ops/c22h4-demo.md`](ops/c22h4-demo.md) |
| ทางถอย trial30 | [`ops/trial30-demo.md`](ops/trial30-demo.md) |
| ผล backtest ทั้งเทป | [`reviews/2026-10-04-four-strategy-continuous-backtest.md`](reviews/2026-10-04-four-strategy-continuous-backtest.md) |

คำสั่งส่งออเดอร์คือ `make bot-execute`. `make bot-run` เป็น shadow.

โค้ดที่อยู่หลังคำสั่งนั้นคือ `scripts/c22h4`. รอบเข้าออเดอร์อยู่ที่ `scripts/trial30`. `scripts/research` ย้ายที่ไม่ได้เพราะแคมเปญแฮชพาธไฟล์. `main.py`, `scripts/smc`, `scripts/webhook`, `scripts/pure_b1` อยู่นอกคำสั่งนี้.

เอกสารแคมเปญเก่า แผน SMC และงานวิจัย B1 อยู่ใน [`archive/`](archive/). ห้ามใช้ไฟล์เหล่านั้นเปลี่ยนสัญญาที่กำลังรัน. `reviews/` เก็บรายงานตรวจที่เป็นหลักฐาน ยังไม่ถูกลบ.
