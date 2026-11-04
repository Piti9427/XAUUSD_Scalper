# Dobby reconstructed vs active C22 — comparison and selection

**เลือกคง C22 บน contract Demo เดิม. Reject Dobby reconstructed สำหรับ replacement.**
Dobby แพ้ net profit และ tick-equity drawdown ทุกคู่เทียบ แม้ basket win rate สูง.
ไม่มีการเปลี่ยน runtime/config, เปิด terminal, เชื่อม broker, ส่ง order จริง,
renew cost attestation, restart watcher หรือ deploy. ไม่ใช่การอนุมัติเงินจริง.

Owner เลือกชัดเจน: “Dobby martingale ตาม parameters ที่ส่งมา แบบ reconstructed และ
research-only”. ไม่มี EA ฉบับเต็มใน repository หรือ Antigravity scratch ที่ค้น;
โค้ดแนบถูกตัดหลายจุด จึงไม่ใช่ native compile/test หรือการพิสูจน์ iRSI/EA parity.

## ผลช่วงเต็มที่รันจริง

ทุนเริ่ม $200 ต่อ strategy. Quotes จริง **2024-09-01T22:05:06.129 UTC ถึง
2026-10-02T20:57:59.885 UTC**: 167,366,065 ticks / 48,367 completed Bid M15 bars.
Primary evaluation window `[2024-09-01,2026-10-03)` UTC. ไม่มี monthly/account reset
ในช่วงเต็ม. นี่คือ archive ที่มีอยู่ ไม่ใช่ข้อมูลถึง18ต.ค.2026.

| Cost view | Strategy | Net USD | Final USD | Max tick-equity DD | Win rate | Positions/baskets | Profit factor |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base+swap | c22 | +291.55 | 491.55 | 39.28% | 48.33% | 120 | 1.277 |
| base+swap | dobby | -200.00 | -0.00 | 100.00% | 86.13% | 346 | 0.924 |
| stress+swap | c22 | +278.71 | 478.71 | 37.82% | 47.41% | 116 | 1.276 |
| stress+swap | dobby | -200.83 | -0.83 | 100.35% | 82.14% | 56 | 0.639 |
| fee_sensitivity+swap | c22 | +288.32 | 488.32 | 38.47% | 48.28% | 116 | 1.284 |
| fee_sensitivity+swap | dobby | -200.84 | -0.84 | 100.35% | 80.85% | 47 | 0.594 |

C22 นับ single positions; Dobby นับ baskets. Dobby base มี146 BUY/200 SELL baskets;
ยอด legs อยู่ใน CSV/ledger. Win rate86.13% ยังได้ profit factor0.924 และหมดทุน
ใน primary simplified model: winning baskets เล็กเมื่อเทียบ losing baskets.
Dobby base จบที่ modeled insolvency2025-04-24; stress จบ2024-10-18.
Negative final balance/เกิน100% DD เป็นผลจำลอง gap/slippage ก่อน settlement ไม่ใช่
ยอดหนี้จริงของบัญชี broker.

**ข้อจำกัดสำคัญ:** primary engine ไม่มี historical broker stop-out threshold ซึ่ง
snapshot ไม่ให้มา จึงบันทึก margin pressure เกิน100% ก่อน modeled insolvencyและ
ติด `broker_margin_model_inconclusive`. ไม่ใช้ตัวเลขนี้อ้างผล execution จริง.
จึงเพิ่ม exploratory whole-basket liquidation ที่ margin level50%/100% แยกprotocol
หลังผลหลัก โดยไม่แก้/retune source/parameters ของ primary run.

Stop-out sensitivity18 cells +18fresh repeats: Dobby net **$−198.85 ถึง−196.12**,
DD **98.12–99.73%**, แพ้ทุก cell. ตรวจ C22 ทุก observed position tick ทั้ง9primary
cells: max used margin/equity **2.633%**, ไม่แตะทั้งสอง thresholds. สมมตินี้ยังไม่
ใช่ broker partial-liquidation/threshold parity แต่ไม่กลับผล selection.

C22 ไม่ได้บวกทุกช่วง: earlier `[2024-09-01,2025-10-01)` base/stress net
−$21.92/−$21.56, fee sensitivity−$24.71. Later `[2025-10-01,2026-10-03)`
+$186.93/+$279.00/+$291.55 ตามลำดับ. แต่ละ subwindow เริ่ม $200 แยกกันพร้อม causal
indicator prefix; ผลช่วงย่อยไม่สามารถนำมาบวกแทน full continuous account.
Dobby ติดลบหนักทั้งสองช่วง. ข้อมูลทั้งหมดเคยถูกเปิดทำresearch จึงไม่มี untouched
holdout หรือคำรับรอง future profitability. C22 DD39.28% ยังสูง.

## Contracts และ reconstruction ที่ตรึงก่อนผลหลัก

- **C22:** active `config/c22h4-demo.json`, ID `1af968e9ac6a26ea`, snapshot
  `RESEARCH-C22-H4EMA200-20261004`. ใช้ canonical `prepare_candidate` และ
  `breakout_replay.replay` เดิมทุก byte; fixed0.01, cap10%, daily10%, one losing
  exit/day, archived BUY/SELL detection, BUY protection off, SELL BE1R.
- **Dobby:** RSI14 mean-seeded Wilder; strict `<30 BUY / >70 SELL`; no crossing
  requirement. หนึ่ง same-direction basket, lot0.01→0.02→0.04→0.08, grid3000points
  ($3ภายใต้ pinned point0.001), TP$8/SL$55, skip Monday initial entries,
  max one basket SL per server day. คง basket SL$55 ไม่ลดให้เข้ากับ C22 cap.
- Missing branches ระบุชัด: management/TP/SL ก่อน entry filters, เพิ่มgridได้หนึ่ง
  legต่อtick, ไม่เปิด first legซ้อน basket; gridยังmanageวันจันทร์/เมื่อspreadสูง.
  Initial entry retryในM15 slotจนspread<=500points/marginผ่าน แล้วค่อยconsumebar.
- Common data contract: UTC Bid M15 จากครบ15M1; ใช้RSIแท่งที่ปิดแล้ว, incomplete
  closed barบล็อก first entryในslotนั้น. เริ่มต้นRSIจาก archive prefix ไม่อ้างว่า
  seedเหมือนterminalที่มี prehistoryอื่น.
- Stored timestamps aware UTC. Primary server-calendar assumption UTC; full
  base/stress sensitivityUTC+2/+3อีก4cells ไม่เปลี่ยนอันดับ. ต้นฉบับ `TimeCurrent`
  ใช้server time ตาม [MQL5 reference](https://www.mql5.com/en/docs/dateandtime/timecurrent).
- Idealized per-observed-tick management; fills/whole-basket closesที่recordedquote
  พร้อม adverse slippage. ไม่มี latency/reject/partial-fill/disconnection/
  terminal coalescing model. Increment daily SLจากbasket SLจริงในsimulation;
  ไม่จำลอง restartที่ล้างcounter. ไม่มี live entrypoint หรือ accountguard bypass.

## Costs และ swap — ทุก economic cell รวม swap

- Base: observed Bid/Ask spread, slippage0, modeled round-trip commission0.
- Stress: เพิ่มspread$0.20/oz แบ่งสองฝั่ง + adverse slippage$0.10/oz ต่อ market fill;
  commission0ตาม frozen comparison assumptions.
- Fee sensitivity: stressข้างต้น + **สมมติ** commission$7/lot round-trip. ไม่ใช่
  broker tariff ที่ยืนยันแล้ว; reserve/chargeต่อlegที่entryเหมือนC22 engine.
- Snapshot swap points mode1: long−567.4 / short0, point0.001, contract100oz/lot,
  tripleWednesday. ใช้ `SwapPolicy.from_broker`, UTCmidnightlabelpreviousbusinessday;
  Thursday00:00 postsWednesdaytriple. Missing/unsupported metadataบล็อกrun.
- Dobby observed swap0ในprimaryไม่ใช่การomit: BUYที่ข้ามUTCdayในledgerมีเพียง
  Sunday→Mondayสองครั้ง ซึ่งcalendarนี้ไม่postswap; overnightSELL rate0. Regression
  ครอบคลุมnonzero modeled swapและcommission; C22 fullswap−$3.9718ทุกcostview.
- Historical swap rates/calendar/entitlement/commission, indicativefeedและactual
  fillยังunverified: **COST_INCONCLUSIVE**. Feeเปลี่ยนadmission/equitypathได้ จึง
  ไม่ตีความfee sensitivityที่netสูงกว่าstressว่าfeeสร้างกำไร.

## เกณฑ์ตัดสินและการใช้ผล

ก่อนrunตรึง: คง incumbentC22 เว้นแต่Dobby solvent, netpositiveและstrictlyสูงกว่าC22,
DDไม่สูงกว่า ในทั้ง9matched window/cost cells; minimum30baskets/cellและcalendar
sensitivitiesต้องไม่กลับผล. Dobbyไม่ผ่านทุกคู่เทียบ. Laterบางcellsมี14–18baskets
เพราะทุนหมดก่อน ไม่ใช่หลักฐานwinrateที่นิ่งพอ.

**Action:** คง active C22 contract/runtimeตามเดิม. Dobbyไม่ถูกต่อเข้ากับ
`make bot-execute` และไม่สร้างliveconfig. Research rankingไม่เปลี่ยน readiness,
known runtime defects หรือ cutover gates; martingaleเดิมขัด fixedlot/singleposition/
10% capด้วย. การเลือกC22คือคำตัดสินภายในคู่เปรียบเทียบนี้ ไม่ได้qualifyกำไรจริง.

## Evidence และ verification

Campaign: [`runs/dobby-vs-c22-2026-10-18/`](../../runs/dobby-vs-c22-2026-10-18/).
Generated artifacts ignoredทั้งหมด; reportนี้เป็น synthesized markdown.

| Requirement | Evidence |
| --- | --- |
| “นำมาเปรียบเทียบ” | [summary.csv](../../runs/dobby-vs-c22-2026-10-18/summary.csv), [results.json](../../runs/dobby-vs-c22-2026-10-18/results.json);22 primary/calendar cells+22 fresh whole-result repeats |
| “ใช้อันที่ดีกว่า” | [decision.json](../../runs/dobby-vs-c22-2026-10-18/decision.json):`retain_c22`;ไม่มีruntime/config change |
| “พร้อมข้อมูลอ้างอิง” | [protocol.json](../../runs/dobby-vs-c22-2026-10-18/protocol.json),42 verified input artifacts,source snapshotsและSHA256; [input verification](../../runs/dobby-vs-c22-2026-10-18/input-verification.json) |
| Frozen C22 parity | Full base/stress+swap metricsตรง archived comparisonเดิม; [validation.json](../../runs/dobby-vs-c22-2026-10-18/validation.json) |
| Basket/event/accounting correctness | `DobbyReplayTests.test_grid_four_legs_and_tick_exit_reconcile_cash`, `test_gap_adds_only_one_leg_per_tick`, `test_price_gap_can_exceed_basket_stop_and_ruin`;1,811 primarybaskets independentgross/cost/cash/DD reconciliation |
| Swap/fees required | `test_swap_and_commission_applied_once_per_leg`, `test_missing_swap_is_blocked`;ไม่มีno-swap economiccell |
| Causal/vector behavior | `test_rsi_seed_extremes_flat_and_prefix_causality`, `test_vectorized_events_match_scalar_oracle`;48 seededrandom BUY/SELLscalar-vectorequivalence cases |
| Calendar/circuit/margin | `test_management_continues_monday_before_new_entry_filter`, `test_daily_sl_blocks_later_entry_and_restart_not_simulated`, `test_margin_rejection_never_increases_initial_lot`, `test_missing_closed_bar_prevents_stale_rsi_entry`, `test_spread_retry_waits_for_acceptable_quote` |
| Broker-model uncertainty | [stopout protocol](../../runs/dobby-vs-c22-2026-10-18/stopout/protocol.json),18cells+18freshrepeats;1,869 additional baskets independently reconciled; [stopout validation](../../runs/dobby-vs-c22-2026-10-18/stopout/validation.json) |
| Regression | `make test`:978 tests/82.796s,OK(skipped2). `make compile deps lint`ผ่าน;newPythonfilesformatผ่าน |

Primary protocol SHA256: `73264d4110d345589154e1532909b137deeaf2c7bf7e69d04c99dcb6750334d0`.
ทุกcellมี `integrity/<case>.json` และ `fresh_full_result_match=true`.
ยอดbasket reconciliationรวมแถวข้ามscenarios ไม่ใช่จำนวนtrade samplesอิสระ.
C22เป็นresearch replayของactive strategy ไม่ใช่actual Demo fillsหรือการจำลอง
process-restart/baseline behaviorทุกสถานะของlive runtime.
รวม **40 economic cells /40fresh full-result matches**, allswap-inclusive.

คำสั่งรันจากrepositoryroot:

```bash
.venv/bin/python -m unittest tests.research.test_dobby_replay -v
.venv/bin/python -m scripts.research.run_dobby_comparison
.venv/bin/python runs/dobby-vs-c22-2026-10-18/verify.py
.venv/bin/python runs/dobby-vs-c22-2026-10-18/stopout_sensitivity.py
```

Checkpoint reuseตรวจsource/protocol/result hashesก่อนใช้;แก้sourceหรือprotocolแล้ว
ต้องใช้campaigndirectoryใหม่ ไม่overwrite frozen evidence. Sensitivity sourcecopies
อยู่ใต้runsและเปลี่ยนเฉพาะ margin-trigger predicate/reason ตามprotocol ไม่แก้engineหลัก.

**Verdict: retain C22 / reject Dobby replacement — Dobby netnegativeและdrawdownรุนแรงทุกคู่เทียบรวมmodeledstop-out sensitivities.**
