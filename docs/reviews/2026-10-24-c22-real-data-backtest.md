# C22: fresh Exness quote replay and profitability scrutiny — 2026-10-24

**ผลรันใหม่: ประวัติรวมบวก ภายใต้ต้นทุนจำลอง; หลักฐานยังไม่พอยืนยันกำไรจริงสม่ำเสมอ.**
Active C22 เดิม `1af968e9ac6a26ea` เริ่ม $200 → **$407.17 (+103.58%)**, 130 positions,
PF **1.171**, win rate **47.69%**, maximum tick-equity DD **39.28%**.
เมื่อเพิ่ม spread/slippage stress: $394.02 (+97.01%), PF1.166, DD37.82%.
**ต.ค. 2026 ถึง23ต.ค. ขาดทุน $97.51/$98.22 ในบัญชีจำลองต่อเนื่อง.**
Real-money prohibition, frozen Demo configuration และ operational approval gates คงเดิม.

## เป้าหมายและทางเลือกที่เล็กสุด

วัด C22 ที่เลือกใช้อยู่ด้วยราคา Bid/Ask ตรวจต้นทางได้ พร้อมรายการเทรดและบัญชีเงินที่รันซ้ำได้.
ใช้ frozen detector และ canonical tick replay เดิม: ลดความเสี่ยงจากการเขียน strategy
ใหม่ใน framework อื่นแล้วได้คนละระบบ. ไม่ค้นหา parameters, ไม่เปลี่ยน entry/exit/risk,
ไม่เปิด MT5 terminal, ไม่ login broker, ไม่ส่งคำสั่ง, ไม่ deploy หรือแก้ runtime.
ไฟล์ที่ผู้ใช้แก้ค้างอยู่ก่อนเริ่มงานคงเดิม; งานนี้เพิ่ม report และ ignored research artifacts.

## ข้อมูลจริงที่ใช้และตรวจแล้ว

- **171,171,013 observed ticks**, 49,729 completed Bid M15 bars.
  Actual range **2024-09-01T22:05:06.129Z → 2026-10-23T20:57:59.517Z**.
  Requested full window `[2024-09-01,2026-10-24)` UTC; วันสุดท้ายของข้อมูลคือ23ต.ค.
- ดึงเดือนต.ค.ใหม่จาก [Exness XAUUSDm monthly archive](https://ticks.ex2archive.com/ticks/XAUUSDm/2026/10/Exness_XAUUSDm_2026_10.zip):
  42,074,205 bytes, **4,442,109 ticks**, 1,536 completed bars. HTTP source metadata,
  original ZIP, SHA256, import audit และ daily tick counts เก็บไว้ครบ.
- October ZIP SHA256 `d4a169554e24f901a86a1b27e3e20f36f986374a89eb08e8f2afe49527fd871a`.
  ดู authoritative digest ใน [download.json](../../runs/c22-real-data-audit-2026-10-24/input/download.json).
- ตรวจ42 original input artifacts ตาม manifest: raw archive provenance, original
  bars/tapes และ source manifests. ไม่สร้าง Ask จาก spread คงที่, ไม่เติม missing bars.
  ตรวจ schema/provider/symbol/UTC, positive finite prices, Ask≥Bid และเวลาเรียงลำดับ.
- **637,161 overlapping October ticks ตรง archive เก่าทั้ง time/Bid/Ask ทุกแถว**.
  Timestamp ซ้ำ10,906แถวเก็บตาม source order; ไม่ deduplicate จนข้อมูลหาย.
- M1 Bid OHLC สร้างจาก ticks; M15 รับเฉพาะช่วงที่มีครบ15M1.
  ไม่อ้างว่า session coverage สมบูรณ์: observed gaps ยังไม่ได้รับรองทุกช่วงด้วย broker calendar.

ต้นทาง [Exness tick-history page](https://www.exness.com/tick-history/) ระบุ public data
เป็น indicative reference. [Exness Help Center](https://get.exness.help/hc/en-us/articles/360021547851-Tick-history)
ระบุว่าเลือก historical server เองไม่ได้และ ticks แต่ละ server อาจต่างกัน.
ดังนั้น **วัดผลจากราคาจริงได้ แต่ยังไม่ใช่ target-account fills หรือ server parity**.

## ตรึง contract และต้นทุนก่อนผล

`config/c22h4-demo.json` และ9 frozen source pins ผ่าน `verify_sources`.
ทางเดิน detector จริง: `C22H4Strategy.frame` → `BarCache.append` → `prepare_candidate`;
replay ใช้ `prepare_candidate` เดียวกัน. Full BarCache signal/rule parity ผ่าน49,729bars;
prefix causality ผ่าน cutoff2025-01-01,2026-01-01,2026-10-07.
อ้างอิง [strategy.py](../../scripts/c22h4/strategy.py#L53),
[runner.py](../../scripts/c22h4/runner.py#L75),
[prepare_candidate](../../scripts/research/reward156_search.py#L154).

Fixed0.01lot, cost-inclusive initial risk cap10%, daily loss10%, one losing exit/day,
single position, no recovery; BUY RSI14 cross25/EMA50/closed H4EMA200,
SL1.5ATR/TP2 rounded R/no protection; SELL prior96breakout/EMA50/closed H4EMA200,
SL2.5ATR/TP3ATR/BE1R. แต่ละ window เริ่ม$200แยกกัน; indicator prefix ไม่ reset.
Full window ไม่มี monthly/account reset. ห้ามบวกผล subwindows แทน continuous account.

| View | ต้นทุนจำลอง |
| --- | --- |
| base+swap | Recorded Bid/Ask spread, commission0, slippage0 |
| stress+swap | Recorded spread +$0.20/oz; adverse slippage$0.10/oz ต่อ market fill; commission0 |
| fee stress+swap | stressข้างต้น +commissionสมมติ$7/lot/round trip ($0.07ต่อ0.01lot) |

ทุก cell ใช้ swap metadata points mode1: long−567.4/short0, point0.001,
100oz/lot, Wednesday triple; calendar สมมติ UTC-midnight ของ preceding business day
(Wednesday debit ลงThursday00:00). Missing/unsupported swap metadata ต้องหยุด.
Full modeled swap−$3.9718ทุกview. Recent8SELL swap0ตาม explicit short rate;
ไม่ได้ละ swap. Historical rates/calendar/entitlement และ commission ยังไม่ผ่าน
broker-history attestation → **COST_INCONCLUSIVE** ทุกผล.
Fee/stress เปลี่ยน admission/equity path ได้; net ที่สูงขึ้นในบางviewไม่ใช่ข้อสรุปว่า fee สร้างกำไร.

## ผลรันใหม่: full continuous account

| View | Net USD | Final USD | Return | Positions | Win rate | PF | Max tick-equity DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base+swap | +207.17 | 407.17 | +103.58% | 130 | 47.69% | 1.171 | 39.28% |
| stress+swap | +194.02 | 394.02 | +97.01% | 126 | 46.83% | 1.166 | 37.82% |
| fee stress+swap | +202.93 | 402.93 | +101.46% | 126 | 47.62% | 1.173 | 38.47% |

Expectancy $1.59/$1.54/$1.61 ต่อposition; longest losing sequence5/6/6.
รายเดือนในรายงาน/กราฟคือ net ต่อclosed trade attributedตามexit month;
ไม่ใช่ month-end mark-to-market equity หรือการรับรองกำไรรายเดือน.
Maximum admitted risk9.9685%/9.7362%/9.9250%, fixedlotไม่เกินcontract.
Full base BUY21positions net+$105.83; SELL109positions net+$101.34.
Full windowทุกviewไม่มี forced end close. Controlและบางsubwindowsใช้ END_OF_SAMPLE
สำหรับ exposure ที่เหลือ; retained ledger ระบุเหตุผลแยก.
เปอร์เซ็นต์นี้เกิดจากทุน$200และfixedlot; ห้าม scale เป็นผลบัญชี Demo ทุนอื่น.

## Scrutiny: จุดที่ทำให้ยังยืนยันกำไรจริงไม่ได้

### Major — ผลกำไรเปลี่ยนตามช่วงตลาดและกระจุกตัว

Earlier `[2024-09-01,2025-10-01)` จาก$200: base/stress/fee net
**−$21.92/−$21.56/−$24.71**. Later `[2025-10-01,2026-10-24)` จาก$200แยก:
+$136.89/+$194.31/+$206.16. ตรวจได้จาก [results.json](../../runs/c22-real-data-audit-2026-10-24/campaign-02/results.json).

ใน full continuous account, **มิ.ย.2026เดือนเดียว +$247.97 base**;
cash contribution เดือนอื่นรวม **−$40.80**. Stress: June+$247.29, เดือนอื่น−$53.27.
นี่คือ attribution จาก actual simulated closing ledger ไม่ใช่ rerun ตัดเดือนออก
หรือพิสูจน์เหตุเชิง causal. กำไรจาก winnersใหญ่เป็นส่วนหนึ่งของstrategy;
หลักฐานนี้ชี้ว่าผลรวมบวกยังไม่แปลว่าสม่ำเสมอข้าม regimes.
ข้อเสนอ: คง frozen contract เพื่อวัด forward; ไม่ retune โดยใช้เดือนล่าสุดซ้ำ.

### Major — ข้อมูลใหม่ไม่ยืนยัน edge และ equity path สำคัญ

**ต.ค.1–23 ใน full continuous account:** 11closed positions, net
**−$97.51/−$98.22/−$98.99** (base/stress/fee).
เฉพาะ exits7–23ต.ค.บนบัญชีต่อเนื่อง:10positions,
**−$50.04/−$50.82/−$51.52**.

แยก recent `[2026-10-07,2026-10-24)` เริ่ม$200ใหม่ พร้อม historical indicator prefix:
8SELL positions, WR50%, net **+$0.75/+$0.22/−$0.34**,
PF1.010/1.003/0.996, DD **18.22%/20.10%/20.26%**.
ต้นทุนcommissionในfeeviewเป็น sensitivity ไม่ใช่ tariff ที่พิสูจน์แล้ว.
8positionsยังน้อย; ค่าPFใกล้1และdrawdownสูงไม่สนับสนุนคำอ้างกำไรสม่ำเสมอ.
ห้ามเลือกแสดงเฉพาะ recentreset ที่เสมอตัวแล้วละบัญชีต่อเนื่องที่ขาดทุน.
Dataใหม่เกิน prior archive acquisition; **ไม่ได้รับรองว่า untouched holdout**
จากทุก agent/experiment และไม่ได้ preregister ก่อนตลาดช่วงนั้นเกิด.

### Major — research replay ยังไม่เท่ากับ target-account execution

ตรวจ economic path จริง:
[replay](../../scripts/research/breakout_replay.py#L14) → completed-bar signal /
first observed quote≤90s → [prepare_entry](../../scripts/research/breakout_entry.py#L28)
→ cost-inclusive cap/margin/daily admission → observed-tick SL/TP/swap/DD
→ completed-M15 fee-inclusive SELL BE → closing ledger.

Live path เพิ่ม [admission](../../scripts/demo_runtime/admission.py#L22):
identity/exposure/history/baseline/cost attestation/risk/margin/order_check
→ durable intent → broker send/reconciliation →
[broker-confirmed lifecycle/BE](../../scripts/demo_runtime/lifecycle.py#L176)
→ final closing deals → journal/notifier.
Replayไม่มี latency/reject/partial fill/disconnection/restart/safety-halt simulation,
historical stops/freeze levels หรือ live first-quote/current-quote slippageทุกสถานะ.
TP fill ที่target และstop fillที่observedquoteเป็น model assumptions;
DDและinitialcapไม่รับรอง maximum realized loss เมื่อเกิด gap.

รายงาน [actual-trading review24ต.ค.](2026-10-24-c22-actual-trading-scrutinize.md)
มี unresolved target-feed/EMA-prefix differences และขาด Oracle C22 fill/close lifecycle.
นั่นคือหลักฐานจาก reviewก่อนหน้า; งานนี้ไม่ได้query remote brokerซ้ำ.
Local trade-note fileที่อ่านในงานนี้มี759records:758BLOCKED+1OWNER_DAY_START,
ไม่มี execution records; ไม่ใช้ localnotesแทน actual broker PnLหรืออ้าง remoteสถานะปัจจุบัน.
ข้อเสนอ: ต้องมี matched target-feed replay/real fills และ realized
profit+commission+swap+fee reconciliation เพื่อปิดช่องว่างนี้.

## Verification และ reproducibility

Successful campaign: **14 economic cells +14 fresh whole-result repeats**;
full/earlier/later/recentอย่างละ3costviews และ archive control2views.
Control2024-09-01→2026-10-03 ตรง saved original28fieldsทุกfield
รวมledger/equity; added observation fieldsแยกไว้ใน
[archive-control-full-parity.json](../../runs/c22-real-data-audit-2026-10-24/archive-control-full-parity.json).
Originalinputs42artifact hashes, all current source pins, input/output/completion hashesผ่าน.
Independent verifier recomputed metrics/cash/gross/commission/swap/calendar,
entry equity/risk/fixedlot/nonoverlap และ exact DD witnessครบ14cells.
คำว่าindependentหมายถึง accounting/metric recomputation; ไม่ใช่ engineอิสระอีกตัว
หรือ independent market samples. 14scenariosใช้ overlapping price history.

Focused regression:
`PYTHONPATH=.:tests/native .venv/bin/python -m unittest tests.demo.test_c22h4_strategy tests.research.test_c22_frequency test_native_frequency_replay`
— **33tests,2.318s,OK**. Initial invocationใช้native module pathผิด;
corrected commandข้างต้นผ่าน. ไม่มี productioncodeเปลี่ยนจึงไม่ได้รันfullsuite/MT5smoke.
Acquisitionattemptแรกขาดoutputsubdirectory; สร้างdirectoryแล้วimportZIPเดิมใหม่ผ่าน.
Campaignattemptแรกหยุดที่harness timezone conversionหลังcontrolbase;
ต้นฉบับ/error/controlartifactsคงไว้. แก้เฉพาะharnessใน`run_audit_v2.py`,
ใช้ fresh`campaign-02`, ไม่เปลี่ยน strategyหรือinputเพื่อตามผล.

```bash
# ตรวจหลักฐานและrecomputeบัญชี/metrics โดยไม่ส่งorders
PYTHONPATH=. .venv/bin/python runs/c22-real-data-audit-2026-10-24/verify.py

# รัน14cellsใหม่ทั้งหมด ตรวจwhole-resultตรงoriginal; outputต้องยังไม่มี
PYTHONPATH=. .venv/bin/python runs/c22-real-data-audit-2026-10-24/verify.py \
  --rerun-output runs/c22-real-data-audit-reproduction-NEW
```

Observed verifier: `PASS 14 cell/repeat/accounting/metric/source/input/completion checks`.
Reproducibility interfaceรันจริงด้วย
`--rerun-output runs/c22-real-data-audit-2026-10-24/independent-rerun`:
**14fresh replaysเพิ่ม ตรงwhole-resultทุกcell**, exit0.
รวม successful42replaysของ14scenarios; ไม่ใช่42independent market samples.
หลักฐาน [reproduction verification](../../runs/c22-real-data-audit-2026-10-24/independent-rerun/independent-verification.json).
Canvas TypeScript checkผ่านด้วย`tsc --noEmit --strict --skipLibCheck`.
Whole-worktree`git diff --check`พบpreexistingCRLF/trailingwhitespaceในtrade notes;
ไม่ได้แก้ไฟล์นั้น. Reportใหม่ตรวจแยกเพื่อไม่รวมnoiseจากงานค้างเดิม.
Protocol SHA256 `a951e713ebeff2dd46eedda2230c6206ce5c539657a09fca69ee6f3d9b3b1cff`.
หลักฐานหลัก: [protocol](../../runs/c22-real-data-audit-2026-10-24/campaign-02/protocol.json),
[independent verification](../../runs/c22-real-data-audit-2026-10-24/independent-verification.json),
[all results](../../runs/c22-real-data-audit-2026-10-24/campaign-02/results.json),
[base trades CSV](../../runs/c22-real-data-audit-2026-10-24/campaign-02/cells/full-base_swap-trades.csv),
[stress trades CSV](../../runs/c22-real-data-audit-2026-10-24/campaign-02/cells/full-stress_swap-trades.csv).
Machine outputsทั้งหมดอยู่ใต้ignored`runs/`; frozenarchiveไม่ถูกแก้.

## Find-skills result

ค้นleaderboardและ`npx skills find "trading backtesting"`.
พบ community [wshobson/agents@backtesting-frameworks](https://skills.sh/wshobson/agents/backtesting-frameworks):
16.7Kinstalls; [source repo](https://github.com/wshobson/agents)41.6Kstars ณตรวจ24ต.ค.2026.
เนื้อหาครอบคลุม look-ahead/overfitting/costs/walk-forward; ไม่ได้พิสูจน์ C22/brokerparity.
งานนี้ไม่ติดตั้ง เพราะ existingfrozenengineตรงstrategyและมีtests/provenanceแล้ว.
หากต้องการติดตั้งแยก: `npx skills add wshobson/agents@backtesting-frameworks`.

**Verdict: research-only / ยังไม่ qualify กำไรจริง — recent costs-sensitive,
continuous Octoberขาดทุน, historical profitกระจุกตัว, target feed/cost/fill parityยังเปิดอยู่.**
Backtestงานนี้เสร็จ; ขั้นถัดไปคือ frozen forward Demoพร้อมbroker-confirmedledger
หลังoperationalreview/ownerapprovalเดิม ไม่ใช่ปรับพารามิเตอร์หรือเพิ่มlotจากผลนี้.

## Owner clarification: survival and growth over the continuous account

Owner clarified that the main outcome is survival and profitable growth from the
original start through the latest available data. Use the full continuous account
as the primary score. Monthly losses and independently reset subwindows diagnose
weaknesses; they do not independently fail a profitable full account.

Current full-account results satisfy **final balance > initial $200** in all three
modeled cost views: $407.17/$394.02/$402.93. The modeled account remains solvent.
This is a measured historical pass for that criterion, separate from broker parity
and future profitability. If the intended criterion instead forbids balance below
$200 at any intermediate time, the incumbent fails: minimum closing balance was
$172.2656 base, $171.4196 stress, $168.7586 fee stress. Base minimum observed equity
was $168.2446. Balance excludes floating PnL; equity is needed for survival/risk.

Recomputed descriptive evidence: [growth-diagnostics.json](../../runs/c22-real-data-audit-2026-10-24/growth-diagnostics.json).
It binds each original full-result SHA256 and adds no economic replay or strategy
change. In the following list, observed weaknesses are verified; proposed remedies
are research hypotheses, not proven improvements.

### 1. Freeze a full-account acceptance rule before modifying parameters

Require the same start/end, causal prefix, initial capital and cost views for every
challenger; preserve equity, daily state and loss counters through the entire run.
Report final net growth, minimum balance/equity, DD and time to recover prior peaks.
Keep the incumbent as the control. No monthly resets, capital top-ups, removed
losing months or final-output filters. Absolute growth/DD acceptance thresholds
remain an owner decision; no new threshold or guarantee is silently adopted here.

### 2. Close feed, execution and cost-model gaps before selecting a challenger

The current replay passes its internal accounting checks but retains the limits
described above. Match broker-exported input, EMA prehistory and execution rules,
then attest commission/swap/calendar. Include delay, rejected fills and stop/BE
constraints as explicit sensitivities where supported. Public archive authenticity
does not establish target-server parity: [Exness documentation](https://www.exness.com/tick-history/).
MetaQuotes also distinguishes trigger and execution prices in accurate tick modes:
[testing features](https://www.metatrader5.com/en/terminal/help/algotrading/testing_features).
Do not tune signals to compensate for an unverified execution assumption.

### 3. Investigate SELL entry quality first

Base SELL: 109 positions, net+$101.336, PF1.090; BUY:21 positions,
net+$105.8332, PF2.223. SELL dominates trade count with much thinner observed edge;
BUY evidence is too small to justify a BUY-only decision. Trace losing SELLs through
breakout depth, existing EMA filters, volatility and adverse excursion before
choosing one additional confirmation/regime hypothesis. Existing H4EMA200/EMA50
filters must not be proposed again as though absent. Evaluate each change through
the full account, since rejected entries change later admission/equity.

### 4. Test profit retention without assuming earlier BE improves returns

Base peak observed equity $548.6192 ended $407.1692, a25.78% peak-to-final giveback;
stress peak-to-final giveback32.40%. Base ledger contains4losing BUYs and7losing
SELLs whose tick MFE reached at least initial risk. BUY protection is intentionally
off; SELL BE activation is evaluated on completed management bars, so an intrabar
1R excursion does not establish a missed valid BE or a bug. Trace
`breakout_replay.py:346` through protection activation and stop update, and match
the live lifecycle before experimenting. Test exit/protection changes separately;
earlier BE/trailing can also remove eventual TP winners. Accept based on full net
growth and DD under both mandatory cost views, not saved-loss examples alone.

### 5. Reduce drawdown and long recovery before increasing exposure

Base maximum DD39.28%; a prior closing-balance peak on2025-05-15 was next recovered
on2026-04-28, about348days. This is a closing-balance peak-to-recovery interval,
not an exact continuous tick-equity underwater duration. Research targeted entry
admission/cooldown or drawdown-related pauses only after identifying the loss
clusters. Preserve fixed0.01, the10% ceiling, daily protections and no recovery
baskets. These hypotheses can skip winners as well as losers; a faster recovery
must be demonstrated by a new continuous paired replay. Increasing lot does not
repair the observed thin SELL edge and would change the risk contract.

### 6. Separate discovery gains from repeatable growth

Predeclare a small candidate set and change one mechanism at a time, then run each
candidate on the same full account with base+swap and stress+swap. Rank full net
growth, survival, DD and recovery together; retain rolling diagnostics on the
continuous path. Use chronological validation and subsequently unexposed data to
test the selected rule without retuning. Existing history is discovery-exposed;
replaying or repartitioning it cannot create a new untouched holdout.

**Verdict: retain the incumbent as the research control; investigate SELL quality,
profit giveback and long recovery after closing model-parity gaps. The current
full-history model passes profitable survival at the endpoint; none of these
proposed parameter changes has yet demonstrated an improvement.**
