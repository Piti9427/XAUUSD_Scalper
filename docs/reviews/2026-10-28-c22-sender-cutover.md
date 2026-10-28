# Selected26b8 sender-only Demo cutover —28October2026

**SOURCE_CUTOVER_VERIFIED; CURRENT_COST_SPEC_BLOCKED.** Ownerอนุมัติรุ่น
`selected-1c0453dcf92db05d` โดยตรงตามT01; actual senderเริ่ม08:46:31UTC /
15:46:31Asia/Bangkok. ไม่มีการเปิด auto-renew, เปลี่ยน terminal/runtime,
watchdog/backup หรือบังคับ order. หลักฐานอยู่ใน
`runs/c22-sender-cutover-2026-10-28/` ซึ่ง ignored/private

## ขอบเขตและผลจริง

| สิ่งตรวจ | ผลที่ observed |
|---|---|
| Package | 87payloads/78Pythoncompile/25sourcebindings; allhashesและsystemdverifyผ่าน |
| Archive SHA256 | `11a8792f05d453664cf33c00f1e0bbfc4c8451ce4f0491152ea9fa1b4eb66a00` |
| Source | New CYCLE releasehash `b445d0b322911c35f312811c82de1b733043c9799f5878e054264a8fc4d1f056`; confighash `b9c771bf64a0b3b219ea92764b4ee0faec6c86078fd4c9e30d30e6eb12bc4036` ตรง staged cohort |
| Sender | PID120130,active/running,execute=true,enabled,NRestarts0 ณ08:47:35UTC |
| Terminal | PID116183/start06:49:04UTC คงเดิม; unit/workingdirectoryเดิม |
| Maintenance | ระงับ admission15.740346seconds; เปลี่ยนเฉพาะ sender unit path |
| Exposure proof | Exclusive SDK pre08:46:25/post08:46:31UTC:positions0/orders0,Demo/USD/hedging,43deals,cash/volume reconciled |
| Fresh flatness | Final exposure requests08:46:25.930/08:46:31.565UTC; readเสร็จประมาณ12msต่อชุด; check<=5secondsก่อน review/start |
| Backup | Read-only consistent126218240bytes; compressed9591397bytes; download/SHA/restore/counts/identityผ่าน; audit106802/kv12/events0/deliveries0 |
| Financial preservation | Full stopped KV digest, cache+sidecar hash และ policy bytesตรงก่อน/หลังprobe; ไม่ restore journalหรือเปลี่ยน cache metadata |
| Source approval | Genuine approved_utc08:46:31.842516UTC; rawreviewSHAตรง persistedacceptance; original Monday armtime/limitationsเดิม |
| First new bar | Contractกำหนด completeM15หลังapproval:09:00UTC/16:00Thai; ไม่ backdate/replay08:45signal |
| Native strategy | Rules26b8bcd69e043653,fixed0.01,entry/SL/TP/BE,daily10%/loss2,cooldown30min,initialrisk10%,UNKNOWN/noresendเดิม |
| Control/probe orders | ไม่มี order_send; history43dealsตรงทั้งสองprobe; ไม่มี forced financial test |

Sender unitก่อน/หลังเหมือนกันหลังnormalizeเฉพาะ release path ไม่เปลี่ยน env,
restart/timeout/guard flags. Terminal/watchdog/backup unit hashesตรงเดิม
New source reviewไม่ได้แปลว่า entryทุกgateผ่าน; `execute=true` คือarmed mode

## ต้นทุนที่ยังบล็อก entry

Actual broker packet08:46:31.577730UTC เทียบกับ unchanged approved policy:

| Field | Policy expected | Broker observed | Gate |
|---|---:|---:|---|
| swap_long,POINTS | -490.8 | -490.0 | `cost.spec / cost_spec_mismatch` |

เทียบครบทุกfieldในstored economic specพบต่าง1field. แม้ observed swapจะติดลบ
น้อยลง กติกาที่ownerเลือกยังต้องตรงเดิมทุกค่า; ไม่มีการยอมรับcostใหม่
ตัวตรวจเทียบ whole policyก่อน admissionทั้งBUYและSELL จึงบล็อกทั้งสองทิศ
ถ้าค่ายังต่างเมื่อถึงจุดตรวจนั้น การรอsignalอย่างเดียวไม่แก้ mismatchนี้

Policy SHA256ยังเป็น
`247cf2a51d96beb5c805aba2daba9e9c45d49cbff5645514e76811c5fd1babd0`,
reviewed25Oct13:25:18.050055UTC,expiry1Nov13:25:18.050055UTC /20:25:18Thai
ไม่มีการเลื่อน reviewed_utc/expiry,ติดตั้ง grant,เปิด renewal,แก้rates/calendar
หรือทำใหม่ให้เหมือน cost attestation

Observed-cost validatorบนexisting historyคืนPASSใน snapshotนี้ เป็นการตรวจ
historyที่มี:43dealsมี native opening magic22261025จำนวน0 จึงยังไม่มีหลักฐาน
native26b8 forward swap/fill/lifecycleจากaccount sampleนี้ ไม่ใช่Swap-Free entitlement
หลักฐาน currentfieldนี้ไม่สามารถย้อนระบุ fieldของสองrefusals27Octได้
Actual raw tariff sourceยังมี missing clauseตามรายงานroot-closure; economic
statusยังCOST_INCONCLUSIVE. การเปลี่ยน policyต้องมี genuine evidence/review
แยกจากสิทธิ์ sender-only cutoverรอบนี้

## Validation และ review

- Immutable sourceเดิมที่ผ่านfull1439tests/skip2; ไม่มี runtime sourceเปลี่ยนรอบcutover
- ตรวจ detector/geometryซ้ำกับsourceปัจจุบัน:49,729bars/2,751entrygeometries,
  raw+cent/base+stress+fee6pathsตรง; ไม่ใช่ economic replayหรือ brokerfill parity
- Independent preflight reviewพบ4ช่องโหว่ในcontrollerก่อนใช้จริง:
  stale exposure timestamp, probe descendantsหลังtimeout, stop-return ambiguity,
  financialkeysไม่ครบ แก้และreviewซ้ำแล้ว ไม่มี remainingblockingfindingที่พิสูจน์ได้
- Actual helpernegativecontrols:180second-old/future/pending/held exposureถูกปฏิเสธ;
  freshflatผ่าน. บนVMทดสอบ selector/cleanupกับowned dummyเท่านั้น ไม่ใช่SDK
  readerจริง; dummyถูกreap,terminal/wineserverไม่เปลี่ยน
- Actual normal probesสองชุดจบแล้วก่อนsenderเริ่ม; timeout/failure rollback
  ไม่ได้เกิดขึ้นจริงในcutoverนี้ จึงไม่อ้าง fault-injection successบนWineทุกกรณี

Source reviewใหม่คง `ARMED_DEMO_TRIAL_WITH_LIMITATIONS` พร้อม actual live-cost
BLOCKED ในreportและ `CURRENT_COST_GUARD_BLOCKED_NO_NEW_COST_ACCEPTANCE`
ไม่อ้าง strict readiness หรือเปลี่ยนข้อเท็จจริงเพื่อให้reviewผ่าน

## Rollback และส่วนที่ยังไม่ qualified

Old9cfc unit/review/policyและconsistentbackupเก็บครบในprivate preparation
ก่อนเริ่มnewsenderหากgateล้ม controllerคืนoldunit/reviewแล้วเริ่มoldmanager
กรณีเริ่มnewsenderไปแล้ว ต้องตรวจowned/UNKNOWNก่อน rollback ห้ามหยุดmanager
ทิ้งposition ห้ามย้อนjournal/cutoff/lossstateหรือrestorefinancialDBเพื่อย้อนผลเทรด

AP deepertrigger และ matchedbefore/after1hour+24hourรวมrolloverยังเปิดอยู่
Sender-only scopeไม่upgrade watchdog/backup และไม่เปิดexternaldelivery
Native signal→fill→BE→close,held-midnight/rebootและforwardprofitยังไม่ qualified
ไม่มีการรับประกันว่ากำไรจะตรงbacktestหรือได้กำไรรายวัน

## Post-approval M15 ที่ตรวจจริง

Audit CYCLE09:00:57.543180UTC บันทึกรอบเริ่ม09:00:03.516632UTC เป็น
`WAIT / no_signal`,failure=null. หลังจากนั้น09:02:09UTCเป็น`WAIT / duplicate_bar`,
last_bar09:00UTC,execute=true,critical=false,ไม่มีactive/halt/outbox
แสดงว่า new-source closed-M15 gateผ่านและประเมินแท่งจริงแล้ว ไม่มีการย้อนเวลา
หรือบังคับsignalให้เข้าorder. Snapshot09:04:15UTCยังมี financialevent rows0

รอบ boundaryนี้ใช้ประมาณ54.03วินาทีระหว่าง captured_utcกับauditutc; ยังไม่ได้
แยก stage latency จึงไม่อ้างว่าเกิดจากCPU/SDKจุดใด ต้องเก็บไว้เป็น performance
follow-upต่อ90second entry window ไม่เพิ่ม toleranceเพื่อปิดผล. แท่งนี้ไม่มีsignal
จึงไม่ใช่หลักฐานว่าปฏิเสธ nativeFULLเพราะcost หรือพิสูจน์ว่าfill/BE/closeผ่าน

Current spec mismatchมาจาก actual exclusive08:46broker proof แยกจาก
no_signal09:00. หากยังต่างเมื่อมีsignalถึงcostvalidation กฎเดิมจะปฏิเสธทั้งสองทิศ

Independent read-only runtime check08:55:19UTC ผ่าน24checks:87payload hashes,
25sourcebindings,actualcohort/CYCLE/reviewacceptance,enabledsender,unchangedterminal/
5unaffectedunits/dropins/financialstate/costexpiry,shadowsinactive และ no renewal
flags. ผลเฉพาะ initial runtime/source ไม่ใช่APหรือnativeforward qualification
