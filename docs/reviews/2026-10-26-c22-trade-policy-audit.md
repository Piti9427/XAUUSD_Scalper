# Selected26b8 — trade rules, pauses, expiry and forgotten-block review

ตรวจแบบ read-only วันที่26ตุลาคม2026 เวลา23:49:59 Asia/Bangkok.
เป้าหมาย: รู้ว่าบอตเปิด/จัดการ/ปิดไม้เมื่อไร และทุกเหตุที่ทำให้หยุดเปิดไม้ใหม่
กลับมาเองได้หรือจำเป็นต้องมี operator. ไม่มีการแก้ strategy, policy, service,
บัญชี, order หรือ source pin ในงานนี้. ไม่มี economic backtest ใหม่.

**Verdict: rules traceable; unattended operation ยังมีช่องว่าง.**
การแก้ที่เล็กที่สุดคือทำให้ entry availability, expiry และเหตุที่ต้องมีคนแก้
มองเห็นได้ชัด แล้วเตรียม renewal จากหลักฐานจริง. ไม่จำเป็นต้องเขียน trading
engine ใหม่หรือยกเลิก risk checks เพื่อแก้ปัญหาเงียบ.

## สถานะที่ยืนยันบน VM

Immutable release `selected-9cfc54a3dc78f0ae`; native Rules
`26b8bcd69e043653`; execution PID52912 และ terminal PID34838 ยัง active,
NRestarts0. ตรวจ10ไฟล์ source/config สำคัญตรง local ทุกไฟล์.
journal ล่าสุด23:49:53ไทย: execute=true, WAIT/duplicate_bar, observed_positions0,
ไม่มี active/safety_halt ใน snapshot. ประวัติ6629 M15, completeH4 364/required201,
cache restored. Watchdog HEALTHY, delivery/health_delivery disabled,
pending_notifications47. ตัวเลข47คือรายการแจ้งที่ค้าง ไม่ใช่47ปัญหาที่ยัง active.
นี่คือสถานะ journal/บริการ/cache ไม่ใช่ SDK position probe ใหม่; ไม่เปิด SDK
reader คู่กับ sender.

กราฟใน Canvas ใช้192แท่งล่าสุดจาก CSV ของ VM ที่คัดลอกและผูก SHA256.
ประกอบ indicator ด้วยฟังก์ชัน canonical บน prefix6629แท่งก่อนตัด192แท่งมาแสดง.
กราฟเป็น Bid OHLC/เส้น indicator และจุดสัญญาณ ไม่ใช่ประวัติ filled orders,
ไม่ใช่ equity curve หรือ backtest รอบใหม่.

## กราฟและสัญญาณ

- ใช้ XAUUSDm, UTC Bid M15 ที่ประกอบจาก completed M1 ครบ15แท่ง.
  partial/current M1 และ incomplete M15 ไม่ใช้; direct MT5 M15 อาจไม่ตรง.
- RSI7 ใช้ rolling7 arithmetic mean gains/losses, flat gain=loss=0 เป็น50.
  ค่า RSI14 ใน frame เดิมไม่ใช่ oscillator ที่ใช้เลือก BUY ของ26b8.
- EMA50 ใช้ EWM span50, adjust=false, min_periods50; slope เทียบ4 observed bars.
- ATR14 ใช้ rolling mean TrueRange14, ไม่ใช่ fixed pips.
- Macro EMA200 ของ H4 ใช้เฉพาะ H4 ที่มี M15ครบ16แท่ง เผยแพร่หลัง H4ปิด.
  runtime ต้องมี completeH4≥201 และค่า macroล่าสุด finite.
- BUY: RSIก่อนหน้า<30→ปัจจุบัน≥30, closeสูงกว่าแท่งก่อน,
  close>EMA50, EMA50สูงกว่า4แท่งก่อน, close>closedH4 EMA200. ต้องครบพร้อมกัน.
- SELL: close<lowต่ำสุดของ48แท่งก่อนหน้า (ไม่รวมแท่งสัญญาณ),
  close<EMA50, EMA50ต่ำกว่า4แท่งก่อน, close<closedH4 EMA200.
  ไม่มี RSI70 SELL gate. กรณีชนกัน canonical ให้ SELL parent priority.
- ใช้ราคาปิดเปรียบเทียบ; ไส้แท่งแตะระดับอย่างเดียวไม่เท่ากับผ่าน.
  เท่ากับ EMA/macro/prior-low ไม่ผ่าน strict inequality.
- ไม่พบ news, ADX/sideways, dedicated Friday/rollover entry filter;
  entry_session=all. ไม่มี standalone fixed max-spread gate.

หลักฐาน: [canonical signals](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/campaign_signals.py:57),
[macro](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/reward156_tuning.py:49),
[runtime history](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/strategy.py:98).

แท่งล่าสุดปิด23:45ไทย: close4019.652, RSI7=35.7025, EMA50=4012.5581,
H4 EMA200=4200.0164, prior48low3988.535. BUY ไม่ผ่าน RSI crossing และ macro;
SELL ไม่ผ่าน breakout/EMA. canonical direction0. จึงยังไม่มีสัญญาณ ณแท่งนี้.

## เปิด order และ SL/TP

ลำดับจริง: source/config/owner review → Demo identity/permissions → account-wide
positions/orders และ complete ledger → valid symbol/spec/quote → completed M15
หลัง approval → strategy/frame → halt/baseline/exposure/duplicate/signal →
daily-loss count/90second window/first quote/cooldown → costs/spec/calendar/drift →
daily equity check → plan/fixed lot/risk/stops/margin → order_check → fresh
account/quote/exposure/capital recheck → persist SENDING → send → reconcile.
บาง cost/readiness checks เกิดก่อนการคำนวณสัญญาณ และบาง checks หลังพบสัญญาณ;
reasonล่าสุดจึงไม่ได้แสดง blockers ที่ซ้อนอยู่ทั้งหมด.

- เปิด market order fixed0.01 lot, ครั้งละหนึ่ง position; positions/pending
  orders ใดๆในบัญชีเมื่อ flat intent ขวาง entry. ไม่มี grid/basket/martingale.
- BUY request ใช้ Ask; SELL ใช้ Bid. Geometry ใช้ risk entry เผื่อ adverse
  slippage0.10 price units ก่อนคำนวณ SL/TP; request priceกับrisk entryต่างกันได้.
- SL ทั้งสองฝั่งห่าง risk entry2.5ATR14 ปัดตาม tick grid.
- BUY TP=3×ระยะ risk-entryถึงSLหลังปัด; SELL TP=1.35×ระยะดังกล่าว.
  Rตรงนี้เป็นระยะราคา ไม่ได้แปลว่าทุกไม้ใช้เงิน10% หรือได้กำไร30%/13.5%.
- ประเมิน risk0.01จาก SL+commission+exit-slippage allowance และ broker profit
  calculator; ต้อง≤10% current equity. ไม่ลดระยะ SL เพื่อฝืนผ่าน.
- projected future swap ไม่ได้ reserve ใน initial risk cap.
- ตรวจ stops/freeze distance, valid lot grid, margin และ broker order_check.
- มีเวลาเข้า90วินาทีหลัง M15ปิด. ราคาเปลี่ยนเกิน allowanceก่อนส่งขวาง entry.
  สัญญาณที่หมดหน้าต่างไม่ถูกไล่ราคาในแท่งถัดไป; ต้องรอสัญญาณใหม่.
- ก่อนส่ง persist intent; timeout/connection/no response เป็น UNKNOWN,
  reconcileกับbrokerก่อน ไม่มี blind resend.

หลักฐาน: [entry geometry](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/breakout_entry.py:28),
[admission/send order](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:22).

## ระหว่างถือและปิด

Brokerถือ SL/TP; client manager ตรวจ fill, volume/direction/SL/TP/cost/risk.
เมื่อครบ M15 ใหม่ ตรวจ first executable quote ของ boundary: profit หลัง declared
commission/slippage≥original filled risk1R จึง activate BE. ไม่ใช้ intrabar high
แตะ1Rแล้วถือว่าผ่าน. เลื่อน SLใกล้ราคาเปิดชดเชย commission/slippage เมื่อ geometry
และ brokerยอมรับ; ต้องเห็น SLจริงก่อนถือว่า BEสำเร็จ. หลังสำเร็จไม่มี trailing ladder.
Native BEไม่รวม accrued/future swap จึงยังอาจจบ netติดลบ.

ปิดปกติเมื่อ brokerทำ SL/TP หรือมีการปิดจากภายนอกแล้ว ledgerยืนยันครบ.
ไม่พบ opposite-signal exit, partial TP, time stop, max holding duration,
Friday flatten, daily profit target หรือกำไรถึงเป้าแล้วปิดทั้งระบบ.
Contract violation เช่น lot/side/SL/TPผิด, filled riskเกินcap หรือ entrycharges
เกินpolicy ทำ safety_halt และพยายามปิดเฉพาะ owned position เมื่อหลักฐานครบ.
Gap/outage/fill slippageทำให้ขาดทุนจริงเกิน modeled SL riskได้.

policy/reviewหมดอายุไม่ใช่เหตุบังคับปิดไม้; active/UNKNOWNไป managerก่อน admission.
แต่ client actionยังต้องมีidentity/connection/quote/spec/exposure/ledgerที่พิสูจน์ได้.
Broker-held SL/TP ไม่เท่ากับการรับประกัน executionขณะระบบล่ม.

หลักฐาน: [manager ordering](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/runner.py:201),
[BE](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/lifecycle.py:188),
[safety](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/lifecycle.py:374).

## ขาดทุนเท่าไรพัก และกลับมาเมื่อไร

1. **ปิดขาดทุน net<0 แม้เพียงเล็กน้อย:** พัก30 elapsed minutes จากเวลาปิดสุดท้าย.
   netรวมprofit+commission+swap+fee. ข้ามวัน/restartยังคงเวลาเดิม.
   first quoteของสัญญาณต้องเกิดหลังครบเวลา; ไม่ค้างสัญญาณเก่าไว้เข้าเมื่อครบพัก.
2. **ครบ2 owned negative completed positions ในวัน UTC:** งดเปิดเพิ่มวันนั้น.
   ไม่จำเป็นต้องแพ้ติดกัน; นับตามวัน final exit. กลับมานับวันใหม่07:00ไทย
   แต่ cooldown/risk/policy/สัญญาณใหม่ยังต้องผ่าน.
3. **equityลด≥10%จาก proven UTC-day baseline:** ห้าม entryขณะเงื่อนไขจริง.
   ไม่บังคับปิดไม้และไม่กัน SL budgetของไม้ถัดไป. ตรวจequityใหม่ทุกครั้ง;
   หาก flatและขาดทุน realizedแล้วโดยทั่วไปต้องรอ baselineวันถัดไป.
   ตัวอย่างทุนต้นวัน200 threshold180; equity182ยังอาจผ่านแล้วเสียไม้ถัดไปเพิ่ม.
   Daily10%จึงไม่ใช่รับประกันว่าวันนั้นเสียไม่เกิน20ดอลลาร์.
4. **0.01 lot riskเกิน10%equity:** skipไม้; กลับได้เมื่อ ATR/price/cost/equity
   ของสัญญาณใหม่ทำให้ riskผ่าน. ไม่มีเวลานับถอยหลังหรือเติมทุนเอง.
5. **DD40%:** ไม่มี live DD40% halt/resumeในnative26b8. เป็น research gate.
   ไม่มี liveพัก24h-auto-resume overlay; studyล่าสุดไม่ได้เลือกเพิ่มเข้าDemo.
6. **safety_halt:** persistข้ามrestart/วัน. ไม่ clearเองแม้ positionปิดแล้ว.
   ต้องตรวจสาเหตุ/ledgerและตัดสินใจปลดอย่างมีหลักฐาน.
7. **UNKNOWN:** reconcileอัตโนมัติเมื่อหลักฐานครบได้ แต่ไม่มี timeoutแล้วเดาส่งซ้ำ.
   บางเส้นทางตั้ง safety_halt เพิ่ม จึงอาจยังห้าม entryหลัง UNKNOWNคลี่คลาย.

หลักฐาน: [loss/cooldown](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/runner.py:30),
[daily gates](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:49),
[daily ledger](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:207).

## ทุกเวลา/อายุหลักฐานที่มีผล

- **Cost v2อายุ168h:** reviewed25Oct13:25:18UTC → expires1Nov2026
  20:25:18ไทย. ตรงขอบเวลายังผ่าน; หลังขอบ1µsไม่ผ่าน (witnessรันแล้ว).
  restartไม่ต่ออายุ. Calendarปัจจุบันมี25Oct–1Nov; วันที่ขาดหยุดentryได้อีกทาง.
  ต้องตรวจต้นทุน/spec/calendarใหม่และปรับ source-bound reviewให้ตรงก่อนใช้.
- **Cost driftก่อนหมดอายุ:** actual closed swapต่างจากmodelเกิน$0.02
  หรือcommission/feeเกินpolicy ขวางentry; swapจริงต่ำกว่าก็ขวาง.
  Current specต่างจากpolicy fieldsก็ขวาง. ไม่autoเปลี่ยนสมมติฐานให้ผ่าน.
- **Owner review:** initial flat acceptanceต้องcapture/approvalใหม่≤5นาที.
  accepted exact reviewอยู่ข้ามrestartได้; ไม่ใช่อายุ5นาทีของบอตที่รันแล้ว.
  ถูกลบ/แก้/account/source/config/policyhashไม่ตรง → blockจนreviewถูกต้อง.
- **Armed start:** 26Oct00:00ไทยเป็นวันเริ่มครั้งเดียว; ต้องมี completedM15
  หลังapproval. ไม่รอ48h/96barsรอบใหม่ทุกrestartของcohortเดิม.
- **Quote:** อายุ0–60s, ห้ามfuture. feedกลับมาสดจึงประเมินต่อได้.
- **Entry window:**90sต่อM15 signal ไม่ใช่policyอายุ90s.
- **Macro gap:** latest closedH4ไม่ครบ16M15 → ไม่ใช้ค่าเก่าข้ามgap.
  รอ valid closedH4ถัดไป; missingมากอาจนานกว่าหนึ่งH4.
- **Bootstrap:** loaded cacheที่ผ่านsource/account/overlapช่วยrestart;
  หากประวัติสั้น retrybootstrapอย่างเร็วทุก60s, bootstrapงานเกิน60sขวางentry.
- **UTC-day baseline:** หากถือไม้ข้าม07:00ไทย ต้องมี equity boundary proof
  requestและresponseในวินาทีแรก. missingproofอาจหยุดentryทั้งวัน.
  ขณะactiveยังmanage; วันถัดไปflatตั้งต้นอาจreconstructได้. Restartไม่สร้าง
  baselineจากequityปัจจุบันเพื่อเพิ่มงบ. ฝาก/ถอน/adjustmentระหว่างวันขวางentry.
- **Protection UNKNOWN180s:** critical/event; ไม่ใช่autoปลดหรือforce resend.
- **Watchdog heartbeat180s:** staleเป็นissue. Generic blockersมีgrace180s
  ก่อนบันทึกincident; safety/criticalพบแล้วurgent. ไม่มีexpiry countdownปัจจุบัน.

หลักฐาน: [cost validity](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/costs.py:9),
[calendar/drift](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/costs.py:105),
[review](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/execution.py:45),
[baseline](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/broker.py:110).

## Findings เรียงความสำคัญ

**P1 — ไม่มี renewal workflow ก่อนpolicyหมดอายุ.** review.checkตรวจcostก่อน
strategy ทุก admission และรวม ValueErrorเป็น `selected_execution_review_invalid`.
ผู้ใช้เห็นservice activeแต่เข้าไม่ได้ไม่มีกำหนด. หมดอายุวันอาทิตย์อาจถูก
quote_staleบังก่อน จนเปิดตลาดจึงเห็นcost/reviewblock. แนะนำexpiry preflight,
เตือนล่วงหน้า72/24/6hและdue taskที่มีowner; renewalใช้หลักฐานใหม่พร้อมreviewhash,
ไม่touchdate ไม่hotreloadครึ่งชุด. ต้องแสดงlast verified/next dueพร้อมกัน.

**P1 — local monitorมีแต่ยังไม่ส่งถึงเจ้าของ.** VMยืนยันdelivery disabled,
ตามownerเดิมเลือกเตรียมก่อน. Localincident47รายการไม่ใช่notificationที่อ่านแล้ว.
แนะนำตัดสินใจช่องทางเมื่อพร้อม; ระหว่างปิดไว้ต้องแสดง DELIVERY_DISABLEDชัดเจน.
TotalVM outageต้องมีobserverนอกVMจึงรู้ได้. งานนี้ไม่เปิดช่องทางให้เอง.

**P2 — flat stale feedถูกจัดเป็นexpected waitโดยไม่ดูเวลา/ageของตลาด.**
evaluate()เช็กreasonquote_stale/flat/criticalfalse แล้วไม่มีissue แม้heartbeatใหม่
และquote_age86400. Pure-function witnessยืนยัน. แนะนำexpected session/holiday
evidenceและbounded stale escalation ไม่ใช้เวลาเงียบเพื่ออนุญาตquoteเก่า.

**P2 — healthกับentry availabilityแยกกันไม่ชัด.** currententry_readyเป็นtrue
เฉพาะSHADOW_ADMIT; execute=trueยังเป็นfalseได้. reasonล่าสุดแสดงเพียงfirst
failure; costexpiryหรือlatchedhaltที่ซ้อนหลังquoteไม่ปรากฏ. แนะนำผลอ่านอย่างเดียว
ที่แสดงliveness, protection, entry availability, blockers, since, next_check,
resume_condition, requires_operator. ไม่เปลี่ยนrequirementของfinancialgate.

**P2 — baselineproofหน้าต่าง1sแคบสำหรับSDKช้า.** codeต้องrequest/responseอยู่
ในวินาทีแรก; poll alignmentช่วยแต่ไม่รับประกันnetworklatency.
แนะนำwatchdogระบุheld-midnight baseline missingและexpectedresumeโดยตรง;
หากต้องเปลี่ยนวิธีพิสูจน์equityต้องdesign/testใหม่ ห้ามสร้างbaselineเอง.

**Risk distinction:** nativeDaily10%เป็นentrythreshold ไม่ใช่prospectiveSLbudget;
ไม่มีliveDD40%breaker. ข้อนี้knowncontract ไม่ใช่แก้bugด้วยการแอบเพิ่มกฎใหม่.
ล่าสุด12-profile studyไม่พบreplacementที่รักษากำไรและลดriskครบตามเป้า จึงคงnative.

## Module design ที่เล็กพอ

คง SelectedStrategy สำหรับ pure signals/geometry, Admissionสำหรับอนุญาตเปิด,
Lifecycleสำหรับowned intent/position, Cost validationสำหรับหลักฐานต้นทุน,
Watchdogสำหรับอ่านสุขภาพ. จุดที่ควรทำให้เป็น deep module คือ **entry availability**:
Interface เดียวคืนสถานะที่operatorเข้าใจพร้อมresume conditionและexpiry.
Implementation รวมเวลาและmappingของผลที่มีอยู่ ไม่สร้างriskengineซ้ำในwatchdog,
ไม่ให้watchdogclearhalt/renewpolicy/sendorder. เก็บcost diagnosticแบบtyped reason
ก่อน ExecutionReviewรวมexception; current genericreasonยังไม่เพียงพอให้localityดี.

ข้อเสนอทั้งหมดเป็น review/design ยังไม่implemented/deployedในงานนี้.

## Validation และ limits

- Read-only SSH snapshot+CSV:10สำคัญตรงlocal; ไม่มี SDK import/order_send.
- Canonical frameจาก6629แท่ง:latestdirection0; H4macroต่างระดับfloatingpoint
  ประมาณ2e-12จากsnapshot ไม่เปลี่ยนstrictsideของแท่งที่ตรวจ.
- Costboundary expiry−1µs/exact/+1µs:ผ่าน/ผ่าน/ไม่ผ่าน.
- Watchdog24h-stale pure witness:market_data_wait=true,issues=[].
- Existing execution tests3PASS; watchdog tests16PASS; strategy/runner/armedtrial/
  lifecycle/cost/boundary tests56PASS รวม75tests. ไม่รันfullsuiteซ้ำ
  เพราะไม่มีการเปลี่ยนruntime. ไม่มีmarketnews/newcosttariffweblookupในงานนี้;
  ไม่อ้างว่าrenewedpolicyหรือbrokerhistoricalcostparityแล้ว.
- แหล่งmachineevidence:
  [VM snapshot](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-trade-policy-audit-2026-10-26/vm-snapshot.json),
  [analysis/exception inventory](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-trade-policy-audit-2026-10-26/analysis.json).
- Native economic reference:
  [verified risk closure](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-10-26-c22-risk-closure.md).
  Real Bid/Ask+modeledswap, exposed-historyselection, COST_INCONCLUSIVE.
  Expiry/review/source/transport availabilityของproductionไม่ได้ถูกจำลองเป็น
  weeklyoperatorpausesในeconomicresult. ห้ามตีความbacktestเป็นguaranteeว่าจะfill
  ทุกสัญญาณหรือมีกำไรในอนาคต.
