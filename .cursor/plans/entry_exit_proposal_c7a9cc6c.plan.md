---
name: Entry exit proposal
overview: ไม่เปลี่ยนจุดเข้าในรอบนี้. RSI และ Donchian มีใน pure_b1_direction แล้ว. ข่าว 0.20 ATR และ Order Block ยังไม่ผ่านเกณฑ์. งานถัดไปคือเทปใหม่ก่อน แล้วค่อย signal-bar และ demo.
todos:
  - id: hold-code
    content: ไม่แก้ pure_b1_direction และไม่ใส่ข่าวหรือระยะทะลุ 0.20 ATR
    status: pending
  - id: new-tape
    content: ได้เทป XAUUSDm Bid/Ask อย่างน้อย 1 ปีที่ยังไม่เคยใช้เลือกกฎ แล้วตรึงกฎก่อนเห็นผล
    status: pending
  - id: hold-demo
    content: ไม่ทำ signal-bar และไม่ต่อ demo จนกว่า backtest จะผ่าน Strict Improvement
    status: pending
isProject: false
---

# จุดเข้าจุดออกหลังปรับแผน

ไม่เปลี่ยน logic จุดเข้าในรอบนี้. Backtest ยังไม่ผ่านเกณฑ์ จึงยังไม่ทำ signal-bar และยังไม่ต่อบัญชี demo ใน `.env`.

## เกณฑ์ที่ยังใช้

ผ่านเมื่อดีกว่า Donchian 48 / TP 3 พร้อมกันทั้งกำไรสุทธิ, tick DD, realized RR และ stress net. Stress คือ extra spread $0.20 กับ slippage $0.10 ต่อ market fill ตาม logic loop ใน session Codex ไม่ใช่การบวกราคาเข้าครั้งเดียว $0.30.

เทป 28 มี.ค.–28 ก.ย. 2026 ยาว 184 วันและใช้เลือกกฎไปแล้ว. ผลใหม่บนเทปนี้ไม่นับว่าผ่านเกณฑ์.

## สิ่งที่มีอยู่แล้ว จึงไม่เพิ่มซ้ำ

`pure_b1_direction` ใน [scripts/strategy.py](scripts/strategy.py) รับเฉพาะปิดแท่งที่ทะลุ high/low เดิม, RSI อยู่ระหว่าง 30 กับ 70, และอยู่ถูกฝั่ง EMA50. ไม่มีสาขาซื้อเพราะ RSI ต่ำกว่า 30 หรือขายเพราะ RSI สูงกว่า 70. Donchian ในฟังก์ชันนี้คือกรอบ breakout ไม่ใช่โซนแนวรับแนวต้านที่ลากมือ.

## สิ่งที่วัดแล้วและไม่รับ

- ระยะทะลุ 0.20 ATR บน core ได้ +154.39% ซึ่งต่ำกว่า +166.81% ของ Donchian 48 / TP 3.
- ระยะทะลุ 0.15, 0.20 และ 0.25 ATR บน Donchian 48 / TP 3 ทำให้ training แย่ลง. เส้น 0.20 เหลือกำไร training $57.53 จาก $302.64 และ stress net ติดลบ.
- ข่าว Tier 1 ยังไม่มีผลบนเทปนี้ และไม่ได้ถูกผูกกับสี่ไม้ที่แพ้. ยังไม่ใส่.
- Order Block, CHoCH, Fair Value Gap และการเข้าแบบเด้งโซนเป็นสัญญา SMC คนละชุด. เก็บไว้หลัง Pure B1 ผ่านเกณฑ์แล้ว.
- เพดานกำไรต่อวันทำให้กำไร breakout หาย. ไม่ใช้.

## ลำดับที่เหลือ

1. เก็บเทป Bid/Ask ของ `XAUUSDm` ที่ยังไม่เคยใช้เลือกกฎ และยาวอย่างน้อย 1 ปี.
2. ตรึงกฎที่จะทดสอบก่อนเปิดเทปนั้น.
3. วัด Strict Improvement เทียบ Donchian 48 / TP 3.
4. ผ่านแล้วค่อยทำ signal-bar และต่อ demo แบบอ่านอย่างเดียวก่อน. ยังไม่ส่งออเดอร์.

บอทใน [main.py](main.py) ยังเข้าด้วย wick ของ `XAUUSDSniperStrategy`. แผนนี้ไม่เปลี่ยนไฟล์นั้น.
