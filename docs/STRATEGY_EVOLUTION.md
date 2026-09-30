# 📈 XAUUSD Scalper: Strategy Evolution & Backtest History

บันทึกการวิวัฒนาการของระบบเทรด การปรับเปลี่ยน Logic, Risk, Fee และผลลัพธ์ Backtest ตั้งแต่เวอร์ชั่นแรกจนถึงปัจจุบัน

## 🔄 Evolution Matrix

| Version | 🧠 Logic (สัญญาณเข้า) | 🛡️ Risk & Money Management | 💸 Fee (ค่าธรรมเนียม) | 📊 Backtest Result (ทุน $200) | 📌 Verdict (บทสรุป) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **V1: Legacy MSS**<br>*(ต้นเดือน ก.ย. 26)* | - Market Structure Shift (MSS)<br>- EMA Cross | - TP คงที่ (Pips)<br>- SL คงที่ (Pips)<br>- คุม Risk 1.5% | ไม่ได้คำนวณ (ใช้ราคา Close ของแท่งเทียน M15) | *ไม่มีบันทึกชัดเจน* (รันบนพอร์ตจำลอง $10,000) | **❌ ยกเลิก:** สัญญาณช้า โดนหลอกช่วงไซด์เวย์บ่อย ไม่เหมาะกับทองคำ M15 |
| **V2: Hybrid Basket**<br>*(กลางเดือน ก.ย. 26)* | - B1 (Donchian 30 Breakout)<br>- RSI14 Guard | - TP 1.5 ATR / SL 0.75 ATR<br>- **เปิดระบบแก้ไม้ (Recovery)** สูงสุด 2 ไม้<br>- Risk 1.5% | คำนวณหลวมๆ (บิดเบือนเพราะติดบั๊กข้ามออเดอร์ตอนทุนต่ำ) | **พอร์ตแตก (-100%)**<br>(รัน Tick-Replay ของจริงพบว่าพอร์ตแตกยับเยิน) | **❌ ยกเลิก:** <br>1. SL 0.75 แคบไป โดน Noise กินฟรี<br>2. ลอจิก Breakout สวนทางกับระบบแก้ไม้ (ไม่เคยได้แก้ไม้)<br>3. ผลกวาดค่าหลอกลวง (False Positive) |
| **V3: Pure B1 (Current)**<br>*(29 ก.ย. 26)* | - B1 (Donchian 30 Breakout)<br>- RSI14 Guard<br>- **เพิ่ม EMA 50 Trend Filter** | - **TP 6.25 ATR / SL 2.5 ATR**<br>- **ปิดระบบแก้ไม้** (รันไม้เดี่ยว)<br>- **เพิ่ม Risk Cap 10%** (ปฏิเสธเทรดถ้าระยะ SL กว้างเกินไป) | **Real Tick-by-Tick**<br>(หัก Spread, Swap, Commission จริง 45 ล้าน Ticks) | **✅ ทุน $200 โตเป็น $884 (+342%)**<br>- Max DD: 34.4%<br>- Win Rate: 37.4%<br>- เทรด 190 ไม้ (รอดตาย 6 เดือนเต็ม) | **🚀 ปัจจุบัน (Production Ready):**<br>ระบบอยู่รอดได้จริง คืนทุนเร็วด้วย TP ที่ยาวขึ้น และป้องกันพอร์ตแตกด้วย Risk Cap 10% |

---

## 🔍 เจาะลึกการเปลี่ยนแปลงสำคัญ (V2 ➡️ V3)

### 1. ทำไมถึงทิ้งระบบแก้ไม้ (Recovery Basket)?
การทดสอบด้วย Tick 45 ล้านจุด พิสูจน์ทางคณิตศาสตร์แล้วว่า **"สัญญาณ Breakout จะไม่เกิดซ้ำในฝั่งเดิมขณะที่ราคากำลังวิ่งสวนทาง"** 
หมายความว่า เมื่อเข้าออเดอร์แล้วผิดทาง ระบบแก้ไม้ (ที่รอสัญญาณเข้าซ้ำ) จะไม่มีวันถูกกระตุ้น ออเดอร์จะถูกลากไปจนโดน SL เสมอ การปิดระบบแก้ไม้แล้วโฟกัสที่ไม้เดี่ยว (Single-Position) จึงแม่นยำกว่า

### 2. ทำไมถึงต้องมี 10% Risk Cap?
ใน V2 พอร์ต $200 แตกเพราะบางครั้งความผันผวนสูง (ATR กว้าง) ทำให้ระยะ SL กว้างมาก เมื่อโดนลากติดกัน 8 ไม้ เงินทุนจึงหมด
ใน V3 เราบังคับว่า **ถ้า SL กว้างจนทำให้การเปิดหลอดต่ำสุด (0.01) ขาดทุนเกิน $20 (10% ของ $200) บอทจะไม่เข้าเทรดเลย** (ปฏิเสธไป 99 ออเดอร์ในระยะเวลา 6 เดือน) นี่คือเกราะป้องกันพอร์ตแตกที่สำคัญที่สุด

### 3. ทำไม Win Rate แค่ 37.4% ถึงกำไรมหาศาล (+342%)?
เพราะเราเปลี่ยน TP จาก 1.5 ATR เป็น **6.25 ATR** (Reward ใหญ่กว่า Risk 2.5 เท่า) 
แม้จะแพ้บ่อย (Win Rate น้อย) แต่เวลาชนะ 1 ครั้ง จะครอบคลุมการแพ้ได้หลายครั้ง (Profit Factor 1.22) เหมาะกับพฤติกรรมราคาทองคำที่เวลาทะลุกรอบ (Breakout) มักจะวิ่งไปได้ไกล


---

## Central Strategy Change Log — 2026-09-30

เอกสารนี้เป็นประวัติกลางแบบ **เพิ่มรายการต่อท้าย**. แต่ละรายการเก็บกฎเดิม,
config ที่ทดลองเปลี่ยน, เหตุผล, ช่วงข้อมูล, ผลลัพธ์ และมติรับใช้.
การทดลองใหม่ต้องมี ID ใหม่; ผลรันเดิมและ config เดิมต้องเก็บไว้.
หากพบข้อมูลผิด ให้เพิ่ม correction ที่อ้าง ID เดิมและหลักฐานใหม่.
หากรับ strategy ใหม่จริง ให้เพิ่ม adoption record ระบุ `from → to` และวันที่
ก่อนปรับ contract ปัจจุบันใน `CORE_STRATEGY.md`. คำว่า implemented หมายถึง
มีโค้ดทดลองแล้ว; คำว่า adopted หมายถึงเลือกแทนกฎเดิมแล้ว.

### LOG-20260930-00 — Correction ของตาราง V3 ด้านบน

**สถานะ: แก้ข้อสรุปย้อนหลัง; เก็บข้อความเดิมไว้เพื่อ audit.**

ตาราง V3 เดิมที่เรียก +342% / $884 ว่าเป็นผล Donchian30 + RSI30–70 + EMA50
และระบุ “Production Ready” ถูก supersede โดยบันทึกนี้.
ผล +341.99% /190 trades /DD34.38% ใช้ archived RSI BUY≤75 /SELL≥25,
ไม่มี EMA50 และมี hypothetical fee0.10R จึงไม่ใช่ผล frozen core.
คำว่า “หัก Spread, Swap, Commission จริง” ในตารางเก่าไม่ใช่หลักฐานต้นทุน
broker ที่วัดครบ; ผล target ที่ตรวจใหม่คือ -33.51% /4 trades.
สถานะ Pure B1: **research only; Demo orders และ real money NO-GO**.

หลักฐาน: [target replay verdict](reviews/2026-09-29-pure-b1-target-replay-verdict.md),
[config search](reviews/2026-09-29-exness-demo-config-search.md).

### กติกาข้อมูลร่วมของ LOG-01 ถึง LOG-05

- Exness Demo `XAUUSDm`, UTC Bid/Ask ticks; M15 จาก M1 ครบ15/15 นาที.
- Full window: `2026-03-28` inclusive → `2026-09-28` exclusive; ทุนเริ่ม$200.
- Training: `2026-03-28` inclusive → `2026-06-28` exclusive; ทุนเริ่ม$200.
  ห้ามนำผล training ไปเรียกผล full window หรือผล validation.
- Base costs: spread ในราคา Bid/Ask, commission0 ตาม Standard assumption,
  ไม่มี added slippage/swap. Historical swap entitlement และ actual fills ยังขาด.
- Logic-loop stress: extra spread$0.20/oz + adverse slippage$0.10/oz ต่อ
  market fill; scenario สมมติ ไม่ใช่ต้นทุนที่ broker วัดให้.
- ทุกชุด fixed0.01 lot, cap10% ของ equity รวม modeled costs, daily admission
  halt40% ของ UTC day-start equity, single position, recovery off.
- Entry quote แรกหลังปิดแท่ง ภายใน90s; replay อายุ quote เป็น0s เมื่อเห็น tick.
  Protective exit ของ logic loop ใช้ quote แรกที่มี แม้ late.
- Realized RR = mean winning net USD / abs(mean losing net USD).
  ไม่ใช่ configured TP/SL ratio. DD เป็น max tick-equity drawdown.
- เทปนี้เคยถูกใช้ค้นค่าแล้ว; ไม่ใช่ untouched holdout.

### LOG-20260930-01 — Frozen core → candidate config comparator

**เดิม:** Donchian30, RSI14 strict30–70, EMA50 on, ATR14,
SL2.5 ATR /TP6.25 ATR. Configured RR2.5.

**ทดลองเปลี่ยน:** Donchian48, RSI off, EMA off, ATR14,
SL2.5 ATR /TP3.0 ATR. Configured RR1.2. Immediate breakout entry,
fixed SL/TP; ไม่มี break-even/trailing/reset/failed-breakout exit.

| Full window / $200 | Frozen core | Candidate48 |
| --- | ---: | ---: |
| Final balance | $132.98 | $533.62 |
| Return | -33.51% | +166.81% |
| Trades | 4 | 266 |
| DD | 36.12% | 56.89% |

**มติ:** candidate เป็น comparator ของงานวิจัย ยังไม่ได้รับใช้แทน frozen core.
กำไรเพิ่มแต่ DD สูงขึ้น. ผลต่างเกิดพร้อมกับ signal filters, TP และ equity path;
ไม่สรุปว่าจำนวนไม้เพิ่มเพราะ TP สั้นลงเพียงอย่างเดียว.
หลักฐาน: [config search](reviews/2026-09-29-exness-demo-config-search.md).

### LOG-20260930-02 — Candidate48 → neighborhood / walk-forward

**ฐาน:** Candidate48 ใน LOG-01.
**เปลี่ยนเพื่อทดลอง:** Donchian40/48/56/64/72 ×TP3.0/3.25/3.5;
SL2.5 ATR, RSI/EMA off. 15 configs.

| Full window / $200 | Return | DD | Trades |
| --- | ---: | ---: | ---: |
| Donchian48 /TP3.5 | +207.74% | 40.58% | 220 |
| Donchian56 /TP3.5 | +233.15% | 42.10% | 225 |
| Donchian48 /TP3.25 | -26.21% | 58.75% | 74 |

Walk-forward เลือก48/3.5 จาก training สำหรับ28มิ.ย.–28ก.ค.:
+52.70%,28 trades,DD43.79%. สองช่วงหลังไม่พบ training row ผ่านเกณฑ์
research DD≤40%, จึงถือ cash. แต่ละช่วงเริ่ม$200 แยก ห้ามทบผลรวม.

**มติ:** ยังไม่รับใช้; บริเวณค่าใกล้กันให้ผลไม่ทนทาน.
หลักฐาน: [walk-forward review](reviews/2026-09-29-exness-walk-forward-tuning.md).

### LOG-20260930-03 — Comparator48 → entry / invalidation / structural SL

**ฐาน:** Candidate48 LOG-01; training net$302.64,DD42.54%,
realized RR1.189,114 trades; stress net$294.00.

**เปลี่ยนเพื่อทดลอง:** 143 configs จาก immediate/confirm/retest entry,
failed-breakout exit1/2 closes, reset ก่อนรับไม้ใหม่, stagnant exit4/8/16 bars,
ATR SL หรือ candle structural SL. TP3 ATR.

ตัวอย่าง training trial55 — snapshot ของกฎทั้งหมดที่เปลี่ยน:

```json
{
  "donchian": 48,
  "rsi": "off",
  "ema": "off",
  "atr_period": 14,
  "stop_atr": 2.5,
  "target_atr": 3.0,
  "entry_mode": "retest",
  "stop_mode": "atr",
  "failed_closes": 0,
  "reset_after_exit": true,
  "stagnant_bars": 16,
  "protect_mode": "off",
  "entry_guard": "off"
}
```

Retest: ภายใน4 completed bars ต้องแตะขอบ breakout เดิมแล้วปิดกลับ
ด้าน breakout; reset: หลังจบไม้ รอแท่งปิดกลับเข้ากรอบเดิมก่อนเข้าใหม่;
stagnant: ถือ≥16 completed bars และ net executable profit≤0 จึงปิด.

**ผล training:** net$173.49,DD23.09%,realized RR2.172,22 trades;
stress net$129.33. DD/RRดีขึ้น แต่กำไรฐานและหลังstressต่ำกว่า comparator.
**มติ:** ไม่ผ่าน; ไม่มี candidate ส่งไป validation; implemented research only.
หลักฐาน: [logic tuning](reviews/2026-09-30-breakout-logic-tuning.md),
[143 trial snapshots](reviews/2026-09-30-breakout-logic-results.json).
Implementation commit: `994d55b`.

### LOG-20260930-04 — Comparator48 → profit protection

**ฐาน:** Candidate48 LOG-01.
**เปลี่ยนเพื่อทดลอง:** 18 configs; break-even/candle-trail/runner ×
immediate/confirm/retest ×ATR/structural SL.
เปิด protection หลังแท่งปิดเมื่อ executable net profit≥0.5 initial admitted R.
Break-even รวมcommissionและexit-slippage; trailing อิง candle low/high±1 tick,
SLต้องแน่นขึ้นและมีผลกับtickถัดไป. Runner ยกเลิกTPหลังvalid stop updateเท่านั้น.

ตัวอย่าง trial4: confirm entry, structural SL จาก extreme ของ breakout และ
entry candle±1 tick, protect_mode=break_even; failed_closes=0,
reset_after_exit=false,stagnant_bars=0,entry_guard=off. Donchian48,
ATR14,RSI/EMA off,TP3 ATR; SLไม่ใช้2.5 ATRใน variant นี้.

**ผล training:** net$94.99,DD56.88%,realized RR3.389,98 trades;
stress net$48.77.
**มติ:** 18ชุดไม่ผ่าน; ไม่รับใช้แทน comparator/core.
หลักฐาน: [follow-up](reviews/2026-09-30-breakout-followup.md),
[full config snapshots](reviews/2026-09-30-breakout-followup-results.json),
run `data/breakout_protection_2026_09_30_v2/`.

### LOG-20260930-05 — Comparator48 → direction / candle quality / runner

**ฐาน:** Candidate48 LOG-01.
**เปลี่ยนเพื่อทดลอง:** 30 configs; buy_only/sell_only/body_dominant/
close_extreme/prior_day × immediate/confirm × off/break_even/runner.
ATR SL2.5,TP3 ก่อนrunner activation.

ตัวอย่าง training trial11 — snapshot ของกฎทั้งหมดที่เปลี่ยน:

```json
{
  "donchian": 48,
  "rsi": "off",
  "ema": "off",
  "atr_period": 14,
  "stop_atr": 2.5,
  "target_atr": 3.0,
  "entry_mode": "immediate",
  "stop_mode": "atr",
  "failed_closes": 0,
  "reset_after_exit": false,
  "stagnant_bars": 0,
  "protect_mode": "runner",
  "entry_guard": "sell_only"
}
```

SELL entry ที่Bid; protection rule ตามLOG-04. เมื่อactiveใช้stopต่ำกว่าเดิม
ตามhighของแท่งปิด+1tickและbreak-evenที่รวมต้นทุน; ยกเลิกTPเมื่อstop updateผ่าน.

| Training / $200 | Comparator48 | SELL-only runner |
| --- | ---: | ---: |
| Net profit | $302.64 | $330.00 |
| Return | +151.32% | +165.00% |
| DD | 42.54% | 20.41% |
| Realized RR | 1.189 | 0.832 |
| Trades | 114 | 47 |
| Stress net profit | $294.00 | $290.11 |

**มติ:** กำไร/DDดีขึ้น แต่RRและstress netไม่ผ่านเกณฑ์เจ้าของ;
ไม่รับใช้,ไม่ส่งcandidateไปvalidation. Correction ของprior_dayที่00:00
ให้อิงวันปิดแท่งบันทึกในreview;ผลรัน`_v2`supersedeผลก่อนแก้.
หลักฐาน: [follow-up](reviews/2026-09-30-breakout-followup.md),
[30 config snapshots](reviews/2026-09-30-breakout-followup-results.json),
run `data/breakout_entry_quality_2026_09_30_v2/`.
Implementation/fix commit: `bc05e27`.

### LOG-20260930-06 — สถานะหลัง191 logic trials / กติกาบันทึกครั้งต่อไป

**Adopted replacement: none.** Frozen research target ยังเป็นDonchian30+
RSI30–70+EMA50,SL2.5/TP6.25. Research comparatorคือDonchian48,RSI/EMAoff,
SL2.5/TP3. Strategyใหม่มีโค้ดและผลทดลองแล้ว แต่ยังไม่มีชุดได้รับมติรับใช้.

การทดลองครั้งต่อไปต้องเพิ่มรายการใหม่ในเอกสารนี้ โดยเก็บ:

1. ID/วันที่ และ `parent/from` ที่ใช้อ้างเทียบ.
2. Full config/rules snapshot,สิ่งที่เปลี่ยนและเหตุผล.
3. Input window,ทุน,risk/cost/fill assumptions,run path,source/input hashes.
4. ผลbaseline→candidate:profit,DD,realized/configured RR,trades,cost stress.
5. Tests/review,ข้อจำกัด และมติ `experimental/rejected/adopted/superseded`.
6. ถ้าadopted:วันที่รับใช้,from→to,config/runtimeที่เปลี่ยนจริงและหลักฐาน.

รายละเอียดทุกtrialอยู่ในJSONที่linkไว้; logกลางเก็บสรุปและsnapshotตัวอย่าง
ที่อ้างIDได้. การเพิ่มlogไม่แปลว่ารับstrategyนั้นไปใช้งานแล้ว.

### LOG-20260930-07 — ตรวจว่า loop จบแล้วมีตัวที่ดีที่สุดให้รับใช้หรือไม่

**parent/from:** LOG-20260930-06. ไม่มี `from → to`.
**เหตุผล:** เจ้าของถามว่าการวนทดสอบจบและได้ strategy ที่ performance ดีที่สุดแล้วหรือยัง ถ้ามีให้ตั้งเป็น contract ใน `CORE_STRATEGY.md`.
**เกณฑ์ที่เคยเลือก:** ต้องดีกว่า Donchian 48 / RSI off / EMA off / SL 2.5 ATR / TP 3 ATR พร้อมกันทั้งกำไรสุทธิ, tick DD, realized RR และ net หลัง cost stress. เกณฑ์นี้ไม่มีคะแนนถ่วง. `dominates()` ใน `scripts/research/breakout_logic.py` ยังบังคับจำนวนไม้ขั้นต่ำ, stress DD ไม่แย่ลง และความเสี่ยงที่รับไม่เกิน 10%.

**สิ่งที่ตรวจ 2026-09-30 โดยไม่ค้นค่าใหม่:**

| ชุด | จำนวน | `training_pass` | `selected` |
| --- | ---: | --- | --- |
| Logic tuning | 143 | ไม่มี | null |
| Profit protection | 18 | ไม่มี | null |
| Entry quality | 30 | ไม่มี | null |

รวม 191. สถานะทั้งสามไฟล์คือ `NO_QUALIFIED_STRATEGY`.

ตัวที่ใกล้สุดในรอบ entry quality คือ training trial 11: immediate, SELL-only, ATR SL 2.5, TP 3, `protect_mode=runner`. ช่วง training 28 มี.ค.–28 มิ.ย. 2026, ทุน $200:

| Training | Comparator 48/TP3 | Trial 11 |
| --- | ---: | ---: |
| Net | $302.64 | $330.00 |
| DD | 42.54% | 20.41% |
| Realized RR | 1.189 | 0.832 |
| Stress net | $294.00 | $290.11 |
| Trades | 114 | 47 |

กำไรและ DD ดีขึ้น. RR และ stress net ไม่ผ่าน. ไม่มีการส่งไป validation.

กริด 15 ชุดเมื่อ 29 ก.ย. ให้กำไรเต็มช่วงสูงสุดที่ Donchian 56 / TP 3.5 = +233.15%, DD 42.10% และ DD ต่ำสุดของกริดที่ Donchian 48 / TP 3.5 = +207.74%, DD 40.58%. ทั้งคู่ยังเกิน research screen DD 40% และไม่ใช่ผลของ loop 191 ชุด. Walk-forward เลือก 48/TP 3.5 แค่ช่วงแรก แล้วสองช่วงหลังถือ cash.

Replay ซ้ำของ comparator 48/TP 3 ในวันเดียวกันตรง archive: training สิ้น $502.64 / 114 ไม้ / DD 42.54%; full path สิ้น $533.62 / 266 ไม้ / DD 56.89%. ช่วง validation ที่เริ่ม $200 ใหม่ได้ +138.94% แต่ DD 47.00%. ช่วง diagnostic ได้ −16.76% จาก 11 ไม้. ตัวเลขนี้ไม่เลื่อน comparator ขึ้นเป็น core.

**มติ: `rejected` / ไม่มี adoption.** Frozen core คงเป็น Donchian 30 + RSI 30–70 + EMA50, SL 2.5 / TP 6.25. Demo orders และเงินจริงยัง NO-GO. รายการ LOG-00 ถึง LOG-06 ไม่ถูกเขียนทับ.
หลักฐาน: [logic results](reviews/2026-09-30-breakout-logic-results.json), [follow-up results](reviews/2026-09-30-breakout-followup-results.json), [walk-forward](reviews/2026-09-29-exness-walk-forward-tuning.md).

### LOG-20260930-08 — Comparator48 → pause BUY while 20% under equity peak

**parent/from:** LOG-20260930-07. ไม่มี `from → to`.
**เหตุผล:** หลุม tick DD ของ comparator อยู่ที่ไม้ BUY ช่วง 15 มิ.ย.–21 ก.ค. 2026 และ daily halt 40% ไม่เคยทำงาน. ทดลองหยุดรับ BUY ชั่วคราวเมื่อ equity หลุดจากจุดสูงตั้งแต่ 20% และยังรับ SELL.

Snapshot ของกฎที่เปลี่ยน. ค่าอื่นเท่า comparator. Configured RR ยังเป็น 3.0/2.5 = 1.2.

```json
{
  "donchian": 48,
  "rsi": "off",
  "ema": "off",
  "atr_period": 14,
  "stop_atr": 2.5,
  "target_atr": 3.0,
  "entry_mode": "immediate",
  "stop_mode": "atr",
  "failed_closes": 0,
  "reset_after_exit": false,
  "stagnant_bars": 0,
  "protect_mode": "off",
  "entry_guard": "off",
  "buy_pause_drawdown": 0.20
}
```

ค่าเริ่มต้นของฟิลด์นี้คือ `0` ซึ่งปิดกฎ จึงไม่เปลี่ยน baseline. ทุน $200 ต่อช่วง. ต้นทุนฐานคือสเปรดใน Bid/Ask, commission 0, ไม่มี slippage หรือ swap ที่วัดได้. Stress คือ extra spread $0.20/oz และ adverse slippage $0.10/oz. เทปเดียวกับ LOG-03: `data/b1_hybrid_baseline_6mo_fixed_2026_09_28` กับ capture `data/b1_hybrid_exness_6mo_fixed_2026_09_28`. รอบนี้ไม่ได้คำนวณ hash ใหม่.

| ช่วง | Arm | Net | Tick DD | Realized RR | Trades | Stress net | Stress DD | Stress trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Training 28 มี.ค.–28 มิ.ย. | Baseline | $302.64 | 42.54% | 1.189 | 114 | $294.00 | 44.87% | 110 |
| Training | Pause BUY | $274.17 | 34.11% | 1.137 | 102 | $263.37 | 37.98% | 97 |
| Full 28 มี.ค.–28 ก.ย. | Baseline | $333.62 | 56.89% | 1.171 | 266 | $179.76 | 58.65% | 263 |
| Full | Pause BUY | $524.81 | 35.45% | 1.159 | 233 | $414.73 | 37.98% | 226 |

เต็มช่วงกำไรสุทธิและ tick DD ดีขึ้น แต่ realized RR ของต้นทุนฐานลดจาก 1.171 เป็น 1.159. Training กำไร, realized RR และ stress net แย่ลง. `dominates()` เป็น false ทั้งสองช่วง. หน้าต่างนี้ยาว 184 วัน ไม่ใช่ backtest 1 ปี. เทป `XAUUSDm` ที่ยาวสุดในเครื่องคือ 1 ม.ค.–25 ก.ย. 2026 ยังไม่ครบ 365 วัน.

ทดสอบ: `test_buy_pause_blocks_buy_under_peak_and_still_admits_sell`. Suite ด้วย `.venv` รัน 688 tests, skipped 2, exit 0. Ruff ผ่านสองไฟล์ที่แตะ. Mypy ไม่ได้ติดตั้งใน `.venv`.

**มติ: `rejected`.** ไม่รับใช้. Frozen core ไม่เปลี่ยน. Strict Improvement ยังไม่สำเร็จ.

### LOG-20260930-10 — Both frozen parents → bounded logic/admission campaign

**parent/from:** Frozen Pure B1 D30 / RSI30–70 / EMA50 / SL2.5ATR / TP6.25ATR, plus Donchian48 / no RSI/EMA / SL2.5ATR / TP3ATR. **to:** research trials only, no adoption.

New research fields: `risk_cap=0.025/0.05/0.10`, `daily_loss_limit=0.05/0.10/0.20/0.40`, `min_depth_atr=0/0.15/0.20/0.25`, either parent's `target_atr`, and `entry_mode=failed_reverse` (close inside frozen originating range within2 completed bars). Existing confirmation, retest and protective exits tested alongside these rules. Fixed0.01 lot, no recovery, cost-inclusive cap<=10%. Frozen indicators and SL retained.

Owner revised acceptance for this campaign: profit/WR higher and DD lower than **both** parents; absolute DD<=20%; realized RR>=1, including common cost stress. Full>=60 trades and each chronological half>=20. Existing184 days are reused discovery, not untouched validation.

**Actual result:** 384 unique configs /8 batches, 0 passing all discovery gates; `NO_QUALIFIED_CANDIDATE`. Every trial stores config, full/half base+stress results, ledger, equity checkpoints, input/source hashes. [Result report](reviews/2026-09-30-strategy-campaign.md), [all config/metric results](reviews/2026-09-30-strategy-campaign-results.json), [protocol](specs/2026-09-30-strategy-campaign.md).

ผล full net / DD / WR / realized RR: comparator **$333.62 /56.89% /48.50% /1.171**; diagnostic trial201 **$428.99 /34.60% /49.33% /1.199**. Trial201 ใช้ D48 เดิม, daily loss limit5%, risk cap10%, SL2.5/TP3ATR, entry immediate. Stress **$411.56 /38.09% /49.10% /1.201**. ยังตก DD20%; ไม่รับใช้. Lowest DD among >=60-trade trials: trial360 DD33.45%, net$187.39, WR43.30%, RR1.524; กำไร/WR ต่ำกว่า comparator.

**Verification:** 695 tests, skipped2; focused34 tests; Ruff/compileall passed. Static type checker unavailable. Two-axis review findings fixed; re-review0 unresolved. Corrupted baseline and selection-metadata resume checks rejected as expected. Code commit `4f66709`.

**มติ:** `NO_QUALIFIED_CANDIDATE`; no adoption, Demo BLOCKED. Need new nonempty tick coverage>=12 months with>=3 months untouched, sourced fees/swap, qualified winner, MQL5 parity and Shadow evidence before Demo review. Prior records retained.

### LOG-20261001-11 — continued research / structure

**from:** LOG-20260930-10 and earlier failed discovery hypotheses. **to:** research contract only. Exact logic/config catalog: [protocol](specs/2026-09-30-structural-strategy-campaign.md); [all trial configs/metrics](reviews/2026-10-01-strategy-continuation-results.json).

**Actual result:** 384 unique configs,0 passing all unchanged full/half/base/stress gates. `NO_QUALIFIED_CANDIDATE`. Local immutable evidence `data/strategy_structure_campaign_2026_09_30`, source snapshots verified against protocol SHA256 `ad198753d6e9eea88b522d5de1a254ab89c5db52c2ac665cc6e709fcaa9d61dd`.

Highest full net among>=60-trade trials (diagnostic, not selected): trial249, net$293.16, DD49.87%, WR23.44%, realized RR5.130. [Full evidence/report](reviews/2026-10-01-strategy-continuation.md).

**มติ:** rejected for discovery; no adoption or Demo orders. Existing184 days reused. Skipped halves in screened trials mean not evaluated, never qualified. Source/protocol/ledger/equity/cost evidence kept separately; prior history retained.

### LOG-20261001-12 — continued research / risk_target

**from:** LOG-20260930-10 and earlier failed discovery hypotheses. **to:** research contract only. Exact logic/config catalog: [protocol](specs/2026-09-30-risk-target-strategy-campaign.md); [all trial configs/metrics](reviews/2026-10-01-strategy-continuation-results.json).

**Actual result:** 384 unique configs,0 passing all unchanged full/half/base/stress gates. `NO_QUALIFIED_CANDIDATE`. Local immutable evidence `data/strategy_risk_target_campaign_2026_09_30`, source snapshots verified against protocol SHA256 `91ebdd5ec6a4840bf41852b133a4c71f337d1b8f41205412b8f2e6b79c934eec`.

Highest full net among>=60-trade trials (diagnostic, not selected): trial57, net$159.43, DD25.71%, WR27.23%, realized RR3.259. [Full evidence/report](reviews/2026-10-01-strategy-continuation.md).

**มติ:** rejected for discovery; no adoption or Demo orders. Existing184 days reused. Skipped halves in screened trials mean not evaluated, never qualified. Source/protocol/ledger/equity/cost evidence kept separately; prior history retained.

### LOG-20261001-13 — continued research / boundary

**from:** LOG-20260930-10 and earlier failed discovery hypotheses. **to:** research contract only. Exact logic/config catalog: [protocol](specs/2026-10-01-boundary-strategy-campaign.md); [all trial configs/metrics](reviews/2026-10-01-strategy-continuation-results.json).

**Actual result:** 384 unique configs,0 passing all unchanged full/half/base/stress gates. `NO_QUALIFIED_CANDIDATE`. Local immutable evidence `data/strategy_boundary_campaign_2026_09_30`, source snapshots verified against protocol SHA256 `69965c57e61b622b3410dd4f6c836fa54b29ce0b3fda066918ed18a7f52aae57`.

Highest full net among>=60-trade trials (diagnostic, not selected): trial30, net$226.53, DD49.05%, WR36.22%, realized RR2.004. [Full evidence/report](reviews/2026-10-01-strategy-continuation.md).

**มติ:** rejected for discovery; no adoption or Demo orders. Existing184 days reused. Skipped halves in screened trials mean not evaluated, never qualified. Source/protocol/ledger/equity/cost evidence kept separately; prior history retained.

### LOG-20261001-14 — continued research / sweep

**from:** LOG-20260930-10 and earlier failed discovery hypotheses. **to:** research contract only. Exact logic/config catalog: [protocol](specs/2026-10-01-sweep-strategy-campaign.md); [all trial configs/metrics](reviews/2026-10-01-strategy-continuation-results.json).

**Actual result:** 384 unique configs,0 passing all unchanged full/half/base/stress gates. `NO_QUALIFIED_CANDIDATE`. Local immutable evidence `data/strategy_sweep_campaign_2026_10_01`, source snapshots verified against protocol SHA256 `8ecf38ce4e7d1d3f8f7970a7260f905d8b37ea80ce97b57f88fc6adc9e1a07f3`.

Highest full net among>=60-trade trials (diagnostic, not selected): trial78, net$36.89, DD82.75%, WR11.71%, realized RR7.780. [Full evidence/report](reviews/2026-10-01-strategy-continuation.md).

**มติ:** rejected for discovery; no adoption or Demo orders. Existing184 days reused. Skipped halves in screened trials mean not evaluated, never qualified. Source/protocol/ledger/equity/cost evidence kept separately; prior history retained.

### LOG-20261001-15 — continued research / pullback

**from:** LOG-20260930-10 and earlier failed discovery hypotheses. **to:** research contract only. Exact logic/config catalog: [protocol](specs/2026-10-01-pullback-strategy-campaign.md); [all trial configs/metrics](reviews/2026-10-01-strategy-continuation-results.json).

**Actual result:** 384 unique configs,0 passing all unchanged full/half/base/stress gates. `NO_QUALIFIED_CANDIDATE`. Local immutable evidence `data/strategy_pullback_campaign_2026_10_01`, source snapshots verified against protocol SHA256 `9c2de40eee25e2a5a74864131df3d819e7ab1fcca51f95d01b60e4be90cf3c53`.

Highest full net among>=60-trade trials (diagnostic, not selected): trial217, net$186.14, DD28.52%, WR31.91%, realized RR2.969. [Full evidence/report](reviews/2026-10-01-strategy-continuation.md).

**มติ:** rejected for discovery; no adoption or Demo orders. Existing184 days reused. Skipped halves in screened trials mean not evaluated, never qualified. Source/protocol/ledger/equity/cost evidence kept separately; prior history retained.

### LOG-20261001-16 — continued research / activation

**from:** LOG-20260930-10 and earlier failed discovery hypotheses. **to:** research contract only. Exact logic/config catalog: [protocol](specs/2026-10-01-activation-strategy-campaign.md); [all trial configs/metrics](reviews/2026-10-01-strategy-continuation-results.json).

**Actual result:** 288 unique configs,0 passing all unchanged full/half/base/stress gates. `NO_QUALIFIED_CANDIDATE`. Local immutable evidence `data/strategy_activation_campaign_2026_10_01`, source snapshots verified against protocol SHA256 `c320c92acb41313dd9a58a63ff8b984661cafbeea0a50eabd4dbf9478c8ab6ad`.

Highest full net among>=60-trade trials (diagnostic, not selected): trial28, net$554.18, DD23.37%, WR55.15%, realized RR1.121. [Full evidence/report](reviews/2026-10-01-strategy-continuation.md).

**มติ:** rejected for discovery; no adoption or Demo orders. Existing184 days reused. Skipped halves in screened trials mean not evaluated, never qualified. Source/protocol/ledger/equity/cost evidence kept separately; prior history retained.


## LOG-20261001-17 — Public tick archives and admission hypothesis

**เดิม:**184วัน2026ถูกค้นซ้ำทั้งหมด; ไม่มี untouched holdout.
**เพิ่ม:** publicXAUUSDm ZIP13เดือนSep2024-Sep2025; discovery10เดือนตรวจ49,581,644ticks/19,050M15; อีก3เดือนยังZIP-only sealed. Historical broker specs/costsยัง assumptions. [Data provenance](reviews/2026-10-01-public-tick-acquisition.md).
**ผล:** activation288บนdiscoveryใหม่0ผ่าน; ไม่แทนcore. เพิ่ม researchrisk_mode=drawdown_steps ลดadmission10→5→2.5%ที่DD10/15%, fixed0.01ไม่เปลี่ยน.336contractsแยกตามspec; รอบใหม่บังคับRRสูงกว่าparentที่มีRR นอกเหนือจากfloor1. ผลแต่ละprotocolเก็บแยก ไม่เขียนทับเก่า. DemoยังBLOCKED.


## LOG-20261001-18 — Admission results, no qualified strategy

**เปลี่ยนวิจัย:** capรับriskตามDD10/15%, fixed0.01; RRstrictcomparisonในprotocol4. **ผล:** publicactivation288, oldtapefloor336, oldtapestrict336, publicstrict336 — รวม1,296evaluations/0ผ่าน. ไม่ใช่1,296uniqueconfigs. [Configs/metrics/protocols](reviews/2026-10-01-public-drawdown-results.md).

**มติ:** rejected; ไม่แทนcore, ไม่เปิดDemo. Audited10เดือน+sealed3ZIP ไม่อ้างว่าverified12เดือนครบ. เก็บทุกprotocol/hash/resultแยก; historyเดิมไม่ถูกเขียนทับ. Full706tests/skipped2ผ่าน; focused45ผ่าน; Ruffผ่าน; mypyไม่มี.
