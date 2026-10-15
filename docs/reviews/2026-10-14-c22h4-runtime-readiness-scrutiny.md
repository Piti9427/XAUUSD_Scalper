# C22H4 runtime readiness scrutiny — 2026-10-14

**Historical review snapshot before local correction:** safety-close/accounting
and status changes are recorded in the [debug fix record](2026-10-14-c22h4-runtime-debug-fixes.md).
Owner retained process-scoped daily-baseline policy and requested clearer blocker
reporting. Review witnesses below describe the pre-fix sources; local validation
does not establish deployment or current broker acceptance.

**Verdict: fix-then-ship สำหรับการรับรอง Demo ที่รันต่อเนื่อง.** พบ safety-close recovery ค้างหลัง confirmed partial close, cost policy ปัจจุบันหมดอายุ และ daily baseline ข้ามหลาย midnight ไม่ต่อเนื่อง. Real money ยังคง PROHIBITED ตาม [CORE_STRATEGY.md:500](/Users/nopparuj/my-agents/XAUUSD_Scalper/CORE_STRATEGY.md:500).

## Intent และทางแก้เล็กสุด

เป้าหมาย: ตรวจว่าบอท C22H4 ที่เปิดด้วย `make bot-execute` มีความพร้อมเข้า order, ควบคุม exposure, reconcile หลัง restart และรายงานผลที่ตรง broker evidence หรือไม่.

ทางแก้เล็กสุด: คง frozen detector/geometry/risk และ strategy seam ของ C22 → trial30 lifecycle; แก้ recovery/observability/accounting ใน shared implementation และทบทวน cost attestation. การสร้าง MQL5 Tester Adapter เป็นงานตรวจกลยุทธ์แยกต่างหาก ไม่ได้แก้ runtime blockers ที่พบ. รีวิวนี้ไม่แก้ production source/config, ไม่ต่ออายุ attestation, ไม่ restart/stop watcher และไม่ส่งคำสั่ง broker.

Trace: Make execution gate → Wine wrapper → C22 CLI/shared CLI → account writer guard → broker identity/exposure/history/spec/quote → completed UTC M15/cache/closed H4 → signal → baseline/daily circuits/costs/geometry/broker risk/margin → order_check → persisted SENDING → order_send → broker reconciliation → Journal transition/outbox → optional notification. Entry/management branches และ unchanged shared code ถูกตรวจด้วย.

## P1 — Confirmed partial safety close ค้างพร้อม exposure ที่เหลือ

**Finding:** `_safety_close` ตั้ง `safety_close_pending=True` แล้วเก็บไว้เมื่อ broker ตอบ `10010`; cycle ถัดไปและ restart รอ confirmation อย่างเดียว ไม่มี recovery path สำหรับ residual position ที่ broker ยืนยันแล้ว ([runner.py:624](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/trial30/runner.py:624), [runner.py:661](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/trial30/runner.py:661), [pending branch:397](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/trial30/runner.py:397)).

**ผลกระทบ:** containment ของ unexpected fill ไม่จบ; owned exposure ยังเปิดและบอทค้าง UNKNOWN. Safety halt กัน entry ใหม่ได้ แต่ไม่ได้ปิด exposure ที่เหลือ.

**Evidence:** public `C22H4DemoRunner.cycle()` กับ real detector และ fixture broker. Inject unexpected filled volume0.02 → safety-close request0.02 → broker confirmed partial close0.01/retcode10010 เหลือ0.01. อีก3cycles และ restart ยัง UNKNOWN, pending=True, send calls คง2 (opening+first close). Full-close control จบ SAFETY_CLOSED/flat. ไม่มี pending broker orders ใน fixture. [probe.json](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22h4-runtime-scrutiny-2026-10-14/probe.json). `10010` หมายถึง completed only in part ตาม [MetaQuotes](https://www.mql5.com/en/docs/constants/errorswarnings/enum_trade_return_codes).

**Suggested change:** persist close request/order identity และ reconcile cumulative closing deals, residual owned volume และ pending orders. เมื่อ confirmed partial completion และไม่มี pending request ให้มี explicit residual-close recovery; ambiguous response ต้องรอ evidence ไม่ resend แบบ blind. ครอบคลุม partial/rejected/timeout/late completion/restart ผ่าน public cycle. ไม่แตะ foreign tickets.

## P1 — Default cost policy หมดอายุ จึงรับ signal ใหม่ไม่ได้

**Finding:** `make bot-execute` ใช้ default `data/trial30-demo-cost-policy.json`; reviewed2026-10-05T20:03:29UTC เกิน24h. Actual validator คืน `invalid_or_stale` ([CLI default:36](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/ops/mt5_wine_trial30.py:36), [expiry:29](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/trial30/costs.py:29)).

**ผลกระทบ:** execution flag=True แต่เมื่อมี signal ที่ถึง admission จะ BLOCKED ก่อน order_send. นี่เป็น guard ที่ทำงานถูกต้อง ไม่ใช่เหตุผลให้ถอด guard.

**Evidence:** current journal heartbeat สด, execute=True, ไม่มี active และไม่มี broker-confirmed events; default file validator ล้มที่เวลาปัจจุบัน แต่ policyเดียวกัน+identityเดิมที่ review+1h ผ่าน. Public-cycle stale-policy signal probe ได้ `BLOCKED/cost_policy_invalid_or_stale`, send calls0. Exact-cache replay พบ3 filtered SELL signals หลัง2026-10-07T15:30UTC แต่ไม่พิสูจน์ watcher uptime/quote/admission ณ timestamps เหล่านั้น. [runtime diagnosis](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22h4-no-order-2026-10-14/diagnosis.json).

**Suggested change:** ตรวจ current account/spec/tariff/evidence แล้วให้ owner re-attest ตาม [runbook:25](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/ops/c22h4-demo.md:25). ห้ามเปลี่ยน timestamp เพื่อ bypass. โชว์ expiry และ readiness blocker แยกจาก execution flag.

## P1 — Daily baseline ไม่รองรับ unattended multi-midnight continuity

**Finding:** process-scoped restart latch ทำงานครั้งเดียว; หลังถือข้าม midnight ถัดไป state.day ยังเป็นวันก่อน และ admission หลังปิดไม้ติด `day_start_floating_unknown` ([broker.py:104](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/trial30/broker.py:104), [broker.py:120](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/trial30/broker.py:120)). Active management กลืน baseline error เพื่อ reconcile ต่อได้ ([runner.py:126](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/trial30/runner.py:126)).

**ผลกระทบ:** bot ที่ process ยังเดินอาจหยุดรับไม้ใหม่หลัง overnight lifecycle. Restart relatches equity ใหม่ จึงเปลี่ยนฐาน daily allowance; ไม่ควรใช้เป็นวิธีบังคับให้ trade.

**Evidence:** rerun probeเดิมกับ current source: FILLED → MANAGING(day1) → MANAGING(day2 แต่ baselineยังday1) → CLOSED → BLOCKED(day_start_floating_unknown). Restart control ได้ WAIT/no_signal ด้วย baselineใหม่;ไม่มี order resubmission. Stronger daily-continuity assertion ล้มตรงเหตุผลที่คาด. [fresh red log](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22h4-runtime-scrutiny-2026-10-14/daily-continuity-red.log). นี่พิสูจน์ fixture path ไม่ใช่การยืนยันสาเหตุของทุก historical blocked note.

**Suggested change:** ownerเลือก daily recovery policy/provenance ก่อนแก้. ถ้าคง process-scoped contract ให้ประกาศ limitation ชัด; ถ้าเปลี่ยน per-day recovery ต้อง update CORE_STRATEGY และทดสอบหลาย midnight/restart โดยไม่ขยาย daily-loss allowance อย่างเงียบ ๆ.

## P2 — Status ซ่อน stale readiness และไม่มี durable per-bar funnel

**Finding:** `bot-status` แสดง “ส่งออเดอร์: ได้” จาก `last_result.execute` อย่างเดียว; detector no-signal/duplicate return ก่อน cost validation. Current status จึง WAIT พร้อม execution flag แม้ default policyใช้ไม่ได้ ([status.py:126](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/ops/trial30_status.py:126), [signal return:144](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/trial30/runner.py:144), [cost gate:161](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/trial30/runner.py:161)). Journal last_result ถูก overwrite ทุก cycle; stdout history ขึ้นกับวิธี launch/redirection ([runner.py:99](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/trial30/runner.py:99)).

**ผลกระทบ:** ownerแยก “เปิด execution” กับ “entry-ready” ไม่ได้ และย้อนยืนยัน signalที่พลาดแต่ละแท่งไม่ได้. Block note counts ไม่ใช่จำนวน distinct signals: dedupe เก็บ reasonล่าสุดหนึ่งค่า จึงเกิด alternating duplicate notes ได้ ([C22 note:173](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22h4/runner.py:173)).

**Evidence:** stale-policy/no-signal public cycle คืน WAIT/no_signal/execute=True/send0 แต่ same-policy validator invalid. เปลี่ยน fixtureให้มี signalแล้วคืน cost_policy_invalid_or_stale. Current status/probe timestamps และ historical notes ตรวจแล้ว.

**Suggested change:** แสดง execution mode, current readiness, last evaluated bar/reason และ cost expiry แยกกัน. Persist one decision record ต่อ completed bar พร้อม direction/filter/admission stage; แยก heartbeat duplicate-bar. ไม่ส่ง phantom FILLED notification และไม่เปลี่ยน strategy predicates.

## P2 — Safety-close cash breakdown และ exit price ไม่อิง close ledger

**Finding:** SAFETY_CLOSED path คืน `profit=net`, commission/swap/fee=0 และใช้ position.price_current แทน last exit deal price ([runner.py:655](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/trial30/runner.py:655)). C22 trade note ใช้ค่าพวกนี้ตรง ๆ ([C22 note:203](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22h4/runner.py:203)).

**ผลกระทบ:** net total ถูก แต่ cost attribution/gross profit และ exit review ผิดหรือไม่ทราบ ทั้งที่มี broker closing evidence. แยกจาก normal CLOSED branch ที่ sum componentsจากledgerถูก.

**Evidence:** costed safety-close fixture: ledger profit−1.00/commission−0.20/swap−0.30/fee−0.10; result net−1.60 ถูก แต่ profit−1.60 และทุกcost=0. Exit price=null แม้ closing dealมีราคา. [probe.json](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22h4-runtime-scrutiny-2026-10-14/probe.json).

**Suggested change:** ใช้ complete position ledger/last exit deal ใน SAFETY_CLOSED เช่นเดียวกับ CLOSED. Regression ต้องตรวจแต่ละ cash component และ actual exit price ไม่ตรวจแค่ผลรวม.

## Acceptance evidence ที่ยังไม่ยืนยัน

Local current status ไม่ใช่ direct broker query. ไม่เปิด MT5 clientเพิ่มบน accountที่มี senderอยู่; process inventory ตรวจไม่ได้ใน sandbox. Canonical history probe outputsไม่พบใน workspaceที่ตรวจ; Oct5 shadow manifestยังระบุ execution_cutover_gates=pending. ไม่ได้พบ acceptance recordใหม่ที่ยืนยัน exact broker/archive parity, >=96 shadow bars spanning midnight และ complete broker-confirmed fill/BE/close lifecycle. ห้ามสรุปว่า ownerไม่ได้อนุมัติจาก missing artifact; userยืนยันเปิด `make bot-execute` แล้ว. Required evidence อยู่ใน [runbook:19](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/ops/c22h4-demo.md:19) และ [cutover gates:38](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/ops/c22h4-demo.md:38).

Entry/risk source pinsยังตรง; reviewed code floor/reject risk, one sender local account guard, aware UTC, SENDINGก่อนsend, UNKNOWNไม่ re-enter และ transactional broker-confirmed state/outbox เป็น protectionsที่ยังคงอยู่. CLIไม่มี notifier enabled; outboxไม่เท่ากับ Telegram delivery. ผล historical swap-inclusive profitability และ native Tester qualification แยกจาก operational readiness นี้.

## Validation และขอบเขต

- Focused existing unit suite: **67 tests /24.599s/OK**, ครอบคลุม C22 strategy/lifecycle/CLI และ trial30 lifecycle/CLI/status; fixture brokerเท่านั้น.
- New public-cycle probes: full safety-close control, partial+restart witness, costed safety-close witness, stale policyมี/ไม่มีsignal. Probe command exit0 หมายถึงยืนยัน counterexamplesสำเร็จ ไม่ใช่ production invariantsผ่าน.
- `probe.py --expect-production-invariants` **expected FAIL**: residual safety exposureและcash component mismatch. `logic_probe.py --expect-daily-continuity` **expected FAIL** ตาม baseline gap. ไม่มี fixถูกนำไปใช้ในรีวิวนี้.
- Raw probes/logs/validation อยู่ใน ignored `runs/c22h4-runtime-scrutiny-2026-10-14/`. Existing owner changesและbackground trade notesคงไว้. No new economic backtest, live broker/order API, attestation update หรือ deployment.

**Verdict: fix-then-ship — safety-close recovery ยังปล่อย confirmed residual exposureค้าง; ต้องแก้และตรวจ operational gates ก่อนรับรอง Demo ต่อเนื่อง. Real moneyยัง PROHIBITED.**
