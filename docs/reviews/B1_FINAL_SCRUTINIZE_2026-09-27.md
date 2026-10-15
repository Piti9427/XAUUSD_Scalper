# B1-FINAL — Implementation vs plan review

วันที่: 2026-09-27 · Commit: `6b39e89` · Scope: review เท่านั้น

**Update หลังแก้ 2026-09-27:** F1/F2/F3/F4/F6 และ exact HWM แก้แล้ว; 585 Python tests และ 127 MQL checks ผ่าน, EA compile 0 errors/0 warnings, target-equity Tester parity 560/560 ส่วน F5 full replay/stress ยัง incomplete รายละเอียดและ experiment ledger: [fix update](../updates/B1_FINAL_FIXES_2026-09-27.md) Findings ด้านล่างเป็นประวัติของ base commit; line numbers เป็นตำแหน่งขณะ review ไม่ใช่ข้อกล่าวหาว่า code ปัจจุบันยังมีทุก defect

**Verdict: REWORK — ยังยืนยันว่า implementation final หรือปิดครบ 8 tickets ไม่ได้ โดยเฉพาะการคำนวณ risk หลัง partial fill และความทนทานของ confirmed-event outbox**

## Intent และทางเลือกที่เล็กที่สุด

เป้าหมาย: ทำ B1 เดิมให้ตรง frozen contract และพิสูจน์ execution/recovery บน Standard Demo ผ่าน Tester โดยแยก implementation, account, strategy และ deployment readiness ออกจากกัน

ทางเลือกที่เล็กที่สุด: เก็บ fixed exit และ `NO_GO` ไว้ แก้ execution/reconciliation/outbox ภายในโมดูลเดิม แล้วปิด evidence gaps ตาม tickets เดิม ไม่จำเป็นต้องเพิ่ม strategy หรือสร้าง execution engine ใหม่ การเพิ่มทุนหรือเปลี่ยน instrument เป็นการตัดสินใจอีกเรื่อง ไม่ใช่วิธีทำ acceptance ให้ผ่าน

แหล่งเทียบ: [PRD](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/specs/b1-final-standard-demo-prd.md), [plan](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/plans/b1-final-standard-demo.md), [tickets](/Users/nopparuj/my-agents/XAUUSD_Scalper/.scratch/b1-final-standard-demo/README.md), [release package](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/research/B1_FINAL_RELEASE_2026-09-27.md), handoff `b1-final-handoff-2026-09-27.md` ที่ผู้ใช้ระบุ

## Findings

### F1 · P1 — Later partial fill ใช้ weighted entry และ commission เก่า ตรวจ risk ต่ำกว่าจริง

**ตำแหน่ง:** [ManagePosition](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEngine.mqh:436), [VerifyFillRisk](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEngine.mqh:401), [Adopt](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEngine.mqh:375)

Path: `Adopt` บันทึก first-fill entry/R/commission → cancel remainder → มี fill เพิ่มก่อน cancel สำเร็จ → `ManagePosition` เปลี่ยนเฉพาะ `pos_volume` → `VerifyFillRisk` ใช้ `pos_entry` และ `pos_commission` เดิม → `ManageExit` ใช้ R เดิม

ตัวอย่างเชิงคำนวณ: BUY requested 0.02 lot, quote 100, SL 95, contract 100, budget $10; fill แรก 0.01 ที่ 100 แล้วอีก 0.01 ที่ 106 ทำให้ average entry = 103, total volume = 0.02, stop risk จริง = $16 แต่โค้ดคำนวณจาก entry 100 ได้ $10 และไม่ trigger over-budget incident ทั้งยังคง R = 5 แทน 8; +2R trigger เป็น 110 แทน 119

**ผลกระทบ:** ขัด risk-protection invariant; cost-covering stop และ close net-R ใช้ฐานผิดได้ กรณีนี้เกิดได้เมื่อ remainder fill แข่งกับ cancel ไม่ใช่ automatic top-up

**หลักฐาน:** source trace + arithmetic ยังไม่ได้รัน MQL fault case นี้; [existing volume-growth test](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEngineTests.mq5:335) เปลี่ยน volume แต่ไม่ได้เปลี่ยน weighted price/fees จึงไม่จับ defect

**แก้ขั้นต่ำ:** refresh cumulative fill volume, weighted entry, initial-SL distance และ cumulative entry commission เป็น snapshot เดียวก่อน risk/exit checks; persist แล้วใช้ในการปิดบัญชี trade เพิ่ม regression ที่ second fill เปลี่ยนทั้ง price และ commission

### F2 · P1 — Adapter ใช้ position ticket กับ position identifier ปะปนกัน

**ตำแหน่ง:** [history recovery](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEA.mq5:170), [EntryCommission / CloseDeal](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEA.mq5:188), [owned-position matching](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEngine.mqh:429)

`OwnedPositions` อ่าน current ticket แต่ `FindFilledPosition` เอา `DEAL_POSITION_ID` ใส่ `filled.ticket`; commission/close history เรียก `HistorySelectByPosition(pos_ticket)` และ engine จับคู่ exposure ด้วย ticket อย่างเดียว

MQL5 ระบุว่า ticket เปลี่ยนจาก server service operation ได้ เช่น swap reopening; identifier คงเดิมตลอด lifecycle และ `HistorySelectByPosition` ต้องรับ identifier ([Position properties](https://www.mql5.com/en/docs/constants/tradingconstants/positionproperties), [HistorySelectByPosition](https://www.mql5.com/en/docs/trading/historyselectbyposition))

**ผลกระทบ:** หลัง ticket เปลี่ยน engine มอง owned position เดิมเป็น unexpected exposure และหา matching position ไม่เจอ; history recovery/commission lookup อาจใช้ key ผิด จึงยังรับรอง interrupted lifecycle ไม่ได้ Fake broker ที่ ticket คงเดิมไม่พิสูจน์ contract นี้

**หลักฐาน:** source trace เทียบ official API contract; ไม่ได้ reproduce server rollover บน broker จริง EA ปัจจุบันถูกจำกัดเป็น Tester-only จึงเป็นข้อบกพร่องที่ต้องปิดก่อนขยายการใช้งาน ไม่ใช่รายงานว่าเกิด loss จริงแล้ว

**แก้ขั้นต่ำ:** แยก persisted `position_identifier` กับ current `position_ticket`; history ใช้ identifier, execution ใช้ current ticket; reconcile ticket จาก identifier และทดสอบ ticket เปลี่ยนระหว่าง restart/close

### F3 · P1 — Producer ทำ confirmed event หายถาวรเมื่อ outbox เขียนไม่สำเร็จ

**ตำแหน่ง:** [JSONL sink](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEA.mq5:304), [close transition](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEngine.mqh:465)

Path: broker close confirmed → `Emit(CLOSE_CONFIRMED)` → FileOpen fail → print journal และ return void → engine `ClearPosition`, `ClearRequest`, `Save` ต่อ จึงไม่มี pending event ให้ replay ภายหลัง ส่วน FileWriteString ไม่ตรวจจำนวน bytes ที่เขียน จึงมี write failure ที่ไม่เพิ่ม counter ด้วย

**ผลกระทบ:** consumer อ่านเฉพาะ JSONL; journal ไม่ได้มี automatic backfill มาเข้าคิว การอ่านย้อนหลังจึงกู้ close card/ledger ไม่ได้ครบ ขัด durable outbox acceptance แม้ execution ไม่ควรถูกหยุดเพราะ notifier ล่ม

**หลักฐาน:** source trace ของ failure branch ไม่ใช่การอ้างว่ารันที่เก็บไว้มี event หายแล้ว

**แก้ขั้นต่ำ:** persist pending confirmed event พร้อม execution transition ด้วย stable event ID แล้ว retry append/deduplicate; ตรวจ write result และเก็บสถานะผิดพลาด ห้ามทำให้ protective close ต้องรอ notification เพิ่ม fault cases file-open fail, short write, crash หลัง close ก่อน append

### F4 · P1 — Release validator ให้ PASS ได้ทั้งที่ event ledger ไม่ครบและ signal ซ้ำ

**ตำแหน่ง:** [reconcile](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/b1_final_release.py:58), [signal_parity](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/b1_final_release.py:35), [implementation verdict inputs](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/b1_final_release.py:213)

**Reproduce ด้วย production functions แล้ว:**

- Broker net +$100 และ −$100, ไม่มี CLOSE_CONFIRMED เลย, equity ไม่เปลี่ยน → `reconcile.passed = true`
- SIGNAL timestamp/direction เดียวกัน 2 events → dict ยุบเหลือ 1 → parity PASS และรายงาน `ea_signals = 1`
- เงื่อนไข `implementation_ok` ไม่อ่าน `RUN_SUMMARY.trusted`, `incident`, `outbox_write_failures`

**ผลกระทบ:** aggregate PnL equality ไม่พิสูจน์ per-trade coverage; signal count ไม่พิสูจน์ absence of duplicates และ unhealthy run ยังมีโอกาสได้รับ `IMPLEMENTATION_VERIFIED` จึงใช้ generated verdict ปิดทุก ticket ไม่ได้

**แก้ขั้นต่ำ:** reconcile broker deals ↔ stable position/request/event identities พร้อม count/coverage และผลราย trade; reject unexpected duplicates ตาม contract; require healthy summary และไม่มี unresolved exposure/events ก่อน verified ไม่ได้สรุปว่าข้อมูลจริงทุก run เสีย—สรุปว่า validator ปัจจุบันพิสูจน์ความครบไม่ได้

### F5 · P2 — Cost/stress ยังไม่ใช่ full replay และ required gate ไม่ครอบคลุม stress matrix

**ตำแหน่ง:** [metrics](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/b1_final_release.py:67), [compare_exits](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/b1_final_release.py:185), [PRD replay/stress requirements](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/specs/b1-final-standard-demo-prd.md:101) / ticket 08

Reserve/adverse เป็น post-hoc deduction; ใช้ max DD/hard-stop จาก unstressed run และไม่ได้เปลี่ยน equity-driven sizing/tiers/entry opportunities ส่วน `GATE_SCENARIOS` บังคับเฉพาะ 0.10R/0.20R ไม่รวม adverse scenarios; spread ×2 ไม่มี ส่วน delay เป็น run แยก ไม่ใช่ combined required stress

**Reproduce แล้ว:** synthetic comparison ที่ 0.10R/0.20R ผ่าน แต่ `0.20R+adverse0.10` ล้ม ยังได้ `passed_required = true` Fixture นี้ทดสอบ gate semantics ไม่ใช่จำลองผลตอบแทนที่เป็นไปได้ของบัญชีจริง

**ผลกระทบ:** DD/risk-path acceptance และ ticket 08 ยังไม่ครบ แม้ handoff เปิดเผย limitation แล้ว การเปิดเผยไม่เท่ากับ acceptance สำเร็จ ปัจจุบัน candidate แพ้ reserve gates และ `costs_measured=False` จึงยังไม่ถูก promote; finding นี้ไม่เปลี่ยนผล NO_GO ปัจจุบัน

**แก้ขั้นต่ำ:** cost/stress ต้องเข้าก่อน replay sizing/HWM/exits, rebuild ledger/marks จากแต่ละ replay; required matrix ต้องมี spread ×2, delay, adverse และ combined cases ตาม PRD Missing evidence ต้องเป็น INCOMPLETE ไม่ใช่ PASS

### F6 · P2 — Consumer crash หลังส่ง ก่อน persist ทำให้ replay ส่งซ้ำ

**ตำแหน่ง:** [consume](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/b1_outbox.py:82)

Path: `sink.send` สำเร็จฝั่งปลายทาง → process ตายก่อน save_state → restart ไม่พบ event ใน delivered set → ส่งซ้ำ TimeoutError มี DELIVERY_UNKNOWN handling แล้ว แต่ crash window นี้ไม่มี persisted in-flight state

**Reproduce แล้ว:** local sink บันทึกว่ารับ card แล้ว raise SystemExit; consume 2 ครั้งบน state path เดิม → `send_calls = 2`, `state_exists = false` ไม่มีข้อความส่งออกภายนอก

**ผลกระทบ:** uncertainty หลัง process crash ไม่ถูกเก็บตาม ticket 07 ไม่ใช่ข้อเรียกร้อง external exactly-once ที่ PRD ไม่ได้สัญญา

**แก้ขั้นต่ำ:** persist SENDING ก่อน network call; หลัง restart เปลี่ยน unresolved SENDING เป็น DELIVERY_UNKNOWN ตามนโยบายไม่ resend อัตโนมัติ; ACK แล้วค่อย persist DELIVERED เพิ่ม crash-boundary regression

## เทียบ 8 tickets

สถานะด้านล่างเป็นผล review ไม่ได้แก้สถานะต้นฉบับใน ticket README

| Ticket | สิ่งที่มี | ผล review / งานค้าง |
|---|---|---|
| 01 Standard Demo target | read-only preflight, actual-equity และ $100 แยกกัน | มีหลักฐานรองรับ acceptance ด้าน identity/sizing; ACCOUNT_BLOCKED เป็นผลที่ยอมรับได้ ไม่ต้องบังคับให้เปิด trade ส่วน fresh-tick UTC ยังเป็น runtime readiness gap ตาม PRD |
| 02 Reference/MQL parity | stored 9,199-bar parity และ incremental-state evidence | มีหลักฐานรองรับ core; ไม่ได้ rerun MQL รอบนี้ F4 กระทบ signal-event comparator แยกจาก indicator parity |
| 03 Baseline lifecycle | Tester lifecycle จาก research fixture; target account reject min lot | Partial: $10,000 fixture ขัด no-capital-increase acceptance ใน ticket 03; ใช้เป็น supplemental engineering evidence ได้ แต่ยังแทน target-account acceptance ไม่ได้ |
| 04 Interrupted execution | fake-broker timeout/restart/partial cases | Partial: F1/F2 ยังเปิด; synchronous Tester ไม่พิสูจน์ broker rollover/recovery ทุกกรณี |
| 05 HWM/risk/protection | tier/latch/corrupt-state checks | Partial: F1 และ persisted HWM padding ต่างจาก exact restart parity |
| 06 +2R cost-covering stop | implemented read-back confirmation; candidate ไม่ผ่าน | ไม่ promote ถูกต้อง; implementation ต้องแก้ F1/F2 และ prerequisite 04/05 ก่อนเรียก final |
| 07 Confirmed notifications | confirmed-only allowlist, acknowledged dedupe, timeout unknown, print sink | Partial: F3/F6 ทำ durability/recovery acceptance ไม่ครบ |
| 08 Freeze validated release | release/runbook/verdict separation | Partial: F4/F5 และ prerequisites ค้าง; README ที่ระบุทุก ticket Done เกินหลักฐาน |

## Plan deviations และข้อจำกัดที่ต้องคงไว้

1. **Persisted HWM เพิ่ม margin 0.05%.** [Save](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEngine.mqh:198) และ restore ใช้ padded peak เป็นจริง ทำให้หลัง restart tier/12% stop อาจเปลี่ยนตรง boundary แม้ conservative ก็ตาม ต้อง persist exact HWM เพื่อผ่าน deterministic contract หรือเสนอเปลี่ยน contract แยก ไม่รับรองเทียบ reference แบบ exact
2. **$10,000 historical fixture ไม่ใช่ target-account approval.** ไม่พบเหตุให้เพิ่มเงินจริง/เปลี่ยนทุนบัญชีจากงาน review นี้; ตัวเลข fixture ใช้ประกอบ engineering เท่านั้น Handoff เองระบุว่าผู้ใช้ยังไม่ได้ยอมรับ scope นี้
3. **Real-tick runs มี generated ticks.** Release ระบุ 1,258 minute bars รวม Sep 25 ทั้งวัน; ต้องเก็บ limitation คู่ผล ไม่เรียกทั้งช่วงว่า observed real ticks ล้วน
4. **Account/strategy constraints ไม่หายไปเมื่อแก้ code.** ตาม stored evidence actual equity ~$1,173.46 มี budget ~$11.73 แต่ cheapest 0.01-lot stop ~$12.16; target run reject 558 signals การ reject ปลอดภัยถูกต้อง ไม่ควร round lot ขึ้น/ลด SL/เพิ่ม risk เพื่อบังคับ sample
5. **Stored profitability evidence ไม่ใช่ qualification.** Fixed fixture +6.89% raw แต่ −2.54% ที่ 0.10R; คง fixed exit frozen, BE disabled และ strategy/deployment NO_GO ตาม release ยังเหมาะสม

## Verification และขอบเขตหลักฐาน

**รันใน review นี้:**

```bash
.venv/bin/python -m unittest tests.test_b1_final_preflight tests.test_b1_final_release tests.test_b1_outbox tests.test_mt5_wine_tester
# 38 tests PASS

.venv/bin/python .scratch/b1-final-review-2026-09-27/reproduce.py
# Four counterexamples reproduced; assertions confirm observed defects.
```

Reproduction artifacts: [script](/Users/nopparuj/my-agents/XAUUSD_Scalper/.scratch/b1-final-review-2026-09-27/reproduce.py), [observed results](/Users/nopparuj/my-agents/XAUUSD_Scalper/.scratch/b1-final-review-2026-09-27/results.json). `.scratch` เป็น local/ignored evidence; เก็บคู่ report หากส่งต่อ

**Code trace:** bars/core → EA OnTick → risk admission → request/partial recovery → SL/TP management → confirmed event producer → consumer → release validator ตรวจ failure branches ข้ามโมดูลด้วย

**ไม่ได้รันใหม่:** 574-test full suite, MetaEditor compile, 106 MQL engine checks, seven MT5 runs และ 9,199-bar MQL parity ตัวเลขเหล่านี้เป็น stored evidence ใน release/handoff ไม่ใช่ fresh verification รอบนี้

ไม่มีการส่ง orders/Telegram, เปิดปิด terminal, เปลี่ยน `.env`, เปลี่ยน strategy/config/implementation หรือแก้ pre-existing dirty files รอบนี้เพิ่มเฉพาะ review artifacts

## งานแก้ตามลำดับ

1. Regression + fix F1/F2 ใน engine/adapter เดิม แล้ว rerun MQL recovery/risk suite
2. ปิด producer durability F3 และ consumer in-flight F6 พร้อม crash/write-failure evidence
3. Harden validator F4; resolve HWM parity; ทำ required replay/stress F5 หรือคง ticket 08 incomplete
4. Rerun scoped acceptance และ regenerate release/ticket status จาก evidence ใหม่ แยก implementation readiness ออกจาก account/strategy NO_GO ต่อไป

**REWORK: ปิด partial-fill risk และ durable-event gaps ก่อน จึงค่อยยืนยัน implementation final; ยังไม่มีหลักฐานให้เปลี่ยน strategy หรืออนุญาต deployment**
