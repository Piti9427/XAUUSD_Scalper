# Core Trading Strategy & Logic (Single Source of Truth)

**Last Updated:** 2026-09-29
**Status:** Research target (Pure B1 Single-Position); live execution NO-GO

เอกสารนี้คือ contract ของ Pure B1 ที่อยู่ระหว่างวิจัย ไม่ใช่คำยืนยันว่าทางเดิน live ใช้กติกานี้แล้ว **หากมีการเปลี่ยนแปลงเงื่อนไขการเทรดใดๆ Agent ทุกตัวต้องมาอัปเดตไฟล์นี้ทุกครั้ง**

---

## 1. ข้อมูลพื้นฐาน (Basic Info)
*   **Symbol:** XAUUSD (Gold); target Exness Demo ใช้ symbol ที่ terminal ยืนยัน (`XAUUSDm` ใน archived capture)
*   **Timeframe:** M15 (กราฟ 15 นาที)
*   **Capital Base:** $200 (Micro-account)
*   **Data/Execution target:** ใช้ Bid OHLC ของ UTC M15 ที่รวมจาก M1 ครบ 15/15 นาทีตาม archived replay. Shadow และ labeled replay ใช้กฎเวลาเดียวกัน `first_fresh_quote_age_60s_lateness_90s`: quote แรกหลังแท่งปิด, อายุไม่เกิน 60 วินาที และมาไม่เกิน 90 วินาทีหลังปิดแท่ง. BUY entry Ask / SELL entry Bid. Direct MT5 M15 อาจมีแท่งช่วงตลาดพักที่ reference ไม่รับ และห้ามป้อน detector. มี read-only Shadow entrypoint แต่ยังไม่มี broker fill หรือ live order path ของ Pure B1. หน้าต่าง 900 วินาทีของ replay เก่าเป็น scenario `archival_first_tick_within_900s` เท่านั้น.

---

## 2. ลอจิกการเข้าเทรด (Entry Logic - Pure B1)
ระบบใช้เงื่อนไข Price Action ผสมกับ Indicator โดยต้องผ่านด่านตรวจ (Gates) ดังนี้:

1.  **Donchian breakout (30):** ราคาปิดทะลุ high/low ของ 30 แท่งก่อนหน้า (ไม่รวมแท่งสัญญาณ)
2.  **RSI Guard (14):** RSI ต้องมากกว่า 30 และน้อยกว่า 70 ทั้ง BUY และ SELL
3.  **EMA Trend Filter (50):**
    *   อนุญาตให้เทรดฝั่ง **BUY** เฉพาะเมื่อราคาปิด *อยู่เหนือ* EMA 50 เท่านั้น
    *   อนุญาตให้เทรดฝั่ง **SELL** เฉพาะเมื่อราคาปิด *อยู่ใต้* EMA 50 เท่านั้น

`scripts/strategy.py:pure_b1_bars` นิยาม indicator ที่ต้องเทียบให้ตรง: prior high/low ใช้ rolling 30 แล้ว shift 1; RSI14 คำนวณ gain/loss ด้วย EWM span 14, `adjust=False`; EMA50 ใช้ EWM span 50, `adjust=False`; ATR14 เป็น rolling mean ของ true range. `scripts/pure_b1/broker_data.py:completed_m15_from_m1` กรองแท่ง M15 ที่ M1 ไม่ครบเช่นเดียวกับ `scripts/research/data.py:bars`. การดึงแท่งใหม่ต้องรักษา UTC index และ warmup/state ให้ตรงกับ replay; ช่วงต้นข้อมูลที่ indicator ยังไม่พร้อมไม่มี signal.

---

## 3. การจัดการความเสี่ยงและต้นทุน (Risk & Fee Math)
Pure B1 ใช้ fixed 0.01 lot เท่านั้น ตรวจความเสี่ยงจาก Stop Loss และต้นทุนแฝงของ Broker (Spread + Commission + Slippage) ก่อนส่งคำสั่ง ห้ามเพิ่ม lot อัตโนมัติ

*   **Take Profit (TP):** 6.25 ATR
*   **Stop Loss (SL):** 2.5 ATR
*   **Pure B1 risk policy:** fixed 0.01 lot ผ่านเมื่อความเสี่ยงรวมไม่เกิน 10% ของ equity; ถ้าเกิน **ปฏิเสธออร์เดอร์** ไม่ลด/เพิ่ม lot
*   **Legacy webhook policy:** `webhook.risk_pct: 0.05` ยังเป็น sizing budget ของ SMC webhook เดิม ไม่ใช่เกณฑ์ปฏิเสธ Pure B1
*   **สมการต้นทุน (Cost Model):**
    `fixed_lot_risk = 0.01 * ((abs(entry - SL) + spread_buffer + slippage_allowance) * contract_size + commission_per_lot)`
    Live gate ต้องใช้ broker-side entry/SL, equity และ symbol contract/volume จริง พร้อม cost model; ไม่บวก spread ซ้ำถ้าราคา entry/SL รวม spread แล้ว

---

## 4. การจัดการออร์เดอร์ (Position & Recovery Management)
*   **Recovery:** ❌ **ปิดการใช้งาน (DISABLED)**
    *   ระบบนี้เป็นไม้เดี่ยว (Single-Position) 100%
    *   ไม่มีการเบิ้ลลอต (No Martingale), ไม่มีการเปิดไม้แก้ (No Grid/Recovery)
    *   อิงตามผล Backtest วันที่ 2026-09-28: โลจิก Breakout แบบแก้ไม้นั้นขัดแย้งกันเองทางคณิตศาสตร์
*   **Daily Circuit Breaker:**
    *   จำกัดการขาดทุนสะสมต่อวัน UTC ไม่เกิน 40% ของ day-start equity (เท่ากับ 40% พอดีให้ปฏิเสธ). Baseline คือ equity ที่บันทึกในวินาทีแรกของ 00:00 UTC พร้อม account fingerprint และ balance. ไฟล์ state ที่อ่านไม่ได้, คนละบัญชี, balance เปลี่ยน, หรือ equity ที่ต่ำกว่า balance โดยไม่มี snapshot ต้อง fail closed. ห้าม reset baseline จาก equity ปัจจุบัน. Labeled replay ไม่ใช้ `day_start.setdefault` ที่ signal tick และไม่ใช้ day quota 99. ถ้า position ลากข้ามเที่ยงคืนโดยไม่มี tick ในวินาทีแรก admission ถูกปฏิเสธ.
*   **Shadow broker gates:** ตรวจบัญชี Demo USD แบบ hedging, quote rule ด้านบน, symbol trade mode, stop/freeze distance, volume 0.01, margin และ broker profit calculation จาก snapshot. Position ที่ไม่มี symbol ต้อง fail closed. Cost policy เวอร์ชัน 1 อยู่ที่ `config/pure_b1_cost_policy.json`: Standard Demo, commission USD ต่อ 1 lot ต่อรอบเที่ยว, แหล่งอ้างอิงและวันที่ตรวจ, slippage เป็น declared assumption ไม่ใช่ค่าที่ terminal รับรอง. `symbol_info` ไม่ให้ commission tariff ก่อนส่งคำสั่ง; ถ้ายืนยันแหล่งไม่ได้ risk admission ปฏิเสธ. Bid/Ask รวม spread แล้ว จึงไม่บวก `spread_buffer`. Swap-free เป็นสถานะปัจจุบัน ไม่ใช่สิทธิ์ย้อนหลัง. ไม่มี `order_send` ใน Shadow. Per-bar parity ledger ณ 2026-09-29 ยัง BLOCKED จึงยังไม่ประกาศว่า Shadow ผ่าน.

## 5. ขอบเขตหลักฐานและการยืนยันผลลัพธ์ (Evidence)

กฎในเอกสารนี้เป็น **research target ที่เลือกศึกษา**; ยังไม่ใช่กลยุทธ์ที่ผ่านเกต Demo automation หรือเงินจริง. ผลย้อนหลังแต่ละชุดต้องระบุ signal, data source, fill/cost model และ risk admission; ห้ามนำผลคนละ contract มาเป็นผลของ target.

1. **ผล OHLC 2.7 ปี +700.4%:** งานคัดเลือกย้อนหลังใช้ public Dukascopy-derived Bid-only bars, entry ที่ signal-bar close และ flat USD 0.30 cost. ไม่มี Exness Bid/Ask fill, slippage, margin approval, swap-free history หรือ broker deal ledger จึงใช้เป็น research screening เท่านั้น. ตัวเลขนี้ไม่พิสูจน์ว่า EMA/RSI จำเป็นหรือทำกำไรได้ภายใต้บัญชีเป้าหมาย. ดู [broker conditions audit](docs/reviews/2026-09-29-xauusdm-broker-conditions-audit.md).
2. **ผล archived Exness tick +341.99%:** ใช้ RSI BUY ≤75 / SELL ≥25 และ **ไม่มี EMA50**; ไม่ใช่ signal contract ในเอกสารนี้. เป็น Python replay ไม่ใช่ order ที่ broker รับและ fill.
3. **ผล target บน Exness ticks ชุดเดียวกัน:** strict RSI 30–70 + EMA50 ได้ **-33.51%** ภายใต้ spread-only และ cost-inclusive 10% cap (4 trades). กรณีสมมติ fee 0.10R พร้อม current-spec swap ได้ **+150.31%** (49 trades) เพราะ fee เปลี่ยนการรับไม้และเส้นทาง equity; ไม่ใช่ค่าธรรมเนียม Standard ที่วัดจริง และไม่ใช่ผลที่คาดของ Standard Demo. ทั้งสองกรณียังไม่วัด broker slippage, margin approval และ historical swap entitlement. แหล่งตัวเลขและ hash ของ input/source: [target replay verdict](docs/reviews/2026-09-29-pure-b1-target-replay-verdict.md) กับ `data/b1_pure_target_replay_cost_gated_2026_09_29/contract.json`.
4. **Labeled replay 2026-09-29** บน input/contract ชุดเดียวกัน ด้วยกฎ quote 60s/90s, day-start ที่ไม่ reset เงียบ และไม่มี day quota 99: Standard/no-commission/swap-free-current-policy **-33.51% / 4 trades**; non-swap-free ได้ตัวเลขเดียวกันเพราะ 4 ไม้ไม่ข้ามเที่ยงคืน UTC และสิทธิ์ swap ย้อนหลังยังไม่มี; slippage/spread stress (declared 0.10 + 0.20, `spread_buffer` 0) **-33.608% / 4 trades**. ไม่ใช่ผล Demo ที่คาดไว้. รายละเอียด: [evidence pin](docs/reviews/2026-09-29-pure-b1-evidence-pin.md) และ [Demo verdict](docs/reviews/2026-09-29-pure-b1-demo-verdict.md).
5. **Parity ledger 2026-09-29:** canonical M15 เทียบ reference ใน overlap 1,812 แท่ง OHLC ตรง, แต่ risk decision ทั้ง 1,812 แท่งถูกบล็อกเพราะไม่มี cost snapshot ที่ตรวจแล้ว. Ledger gate คือ BLOCKED. Shadow ยังไม่ผ่าน. Direct M15 มี 27 แท่งที่ canonical 15/15 ไม่รับ.
6. **มติปัจจุบัน:** เลือก Donchian 30 + RSI 30–70 + EMA50, TP 6.25 ATR / SL 2.5 ATR, fixed 0.01 lot, 10% cap, daily 40% เป็น contract เป้าหมาย **เพื่อวิจัยต่อ**. Demo orders และเงินจริงเป็น NO-GO. `main.py` ยังรัน legacy wick strategy ไม่ใช่ Pure B1.
7. **ตัวเลือกจาก config search 2026-09-29:** บน tick Exness ชุดเดียวกัน โดยใช้สเปรด Bid/Ask และ commission 0 ตามเรท Standard ไม่ใส่ fee สมมติ Donchian 48 ที่ไม่มี RSI และไม่มี EMA50, SL 2.5 ATR, TP 3.0 ATR ได้ +166.81% ($533.62, 266 ไม้, DD 56.89%) และเป็นบวกทั้งสองครึ่งช่วง. Core ปัจจุบันบนรันเดียวกันยังเป็น -33.51%. ตัวเลือกนี้ยังไม่แทน contract ด้านบน และยัง NO-GO สำหรับออเดอร์. รายละเอียดอยู่ที่ [config search](docs/reviews/2026-09-29-exness-demo-config-search.md).

8. **Retrospective walk-forward tuning 2026-09-29:** ตรวจ raw capture 45,671,201 ticks ตรง tape และสร้าง canonical M15 12,100 แท่งกลับได้ตรง reference. Grid 15 ชุด (Donchian 40/48/56/64/72, TP 3.0/3.25/3.5, SL 2.5, RSI/EMA off) ยังไม่มีชุดผ่าน research DD ≤40% บน full window. Donchian 48/TP 3.5 ได้ +207.74%, DD 40.58%; 56/TP 3.5 ได้ +233.15%, DD 42.10%. Walk-forward เลือก 48/3.5 ในช่วงแรก ได้ +52.70% แต่ DD 43.79%; สองช่วงหลังไม่มี training candidate ผ่านเกณฑ์ จึงถือ cash. ทั้ง tape เคยใช้ค้นค่าแล้ว ไม่ใช่ untouched holdout; เกณฑ์ 40% เป็น research screen ไม่ใช่ risk tolerance สำหรับ live ที่เจ้าของอนุมัติ. **ยังไม่เปลี่ยน frozen contract หรือเปิด orders.** ดู [walk-forward tuning](docs/reviews/2026-09-29-exness-walk-forward-tuning.md).


## 6. Offline logic tuning loop (2026-09-30)

Research implementation: `scripts/research/tune_breakout_logic.py` and
`scripts/research/breakout_logic.py`; no order or notification API.
Baseline remains Donchian 48 / ATR14 / SL 2.5 ATR / TP 3 ATR, RSI/EMA off,
fixed 0.01 lot, 10% cost-inclusive equity cap, UTC daily admission halt 40%.
This is an experimental comparator, not a replacement for the frozen target above.

143 unique research combinations tested: immediate/confirm/retest entry,
failed-breakout exit after one/two closes, reset after exit, 4/8/16-bar
no-progress exit, and ATR versus structural SL. Structural SL uses original
breakout and entry candle extremes plus one tick; invalid or over-cap entries
are rejected, never clamped. Protective exits use first available quote after
close even when entry-lateness gate would reject a new entry. Entry quote
lateness remains <=90 seconds.

Result: **NO_QUALIFIED_STRATEGY** under owner-selected strict improvement in
net profit, DD, realized RR and cost-stressed net. All candidates earned less
training net than baseline. Best candidate training net $173.49 versus $302.64;
DD 23.09% versus 42.54%; realized RR 2.172 versus 1.189; stress net $129.33 versus
$294.00. No candidate validation or promotion followed. Full baseline reproduced
$533.621 / 266 trades / DD 56.8941%. Costs, search bias, tests and evidence:
[logic tuning verdict](docs/reviews/2026-09-30-breakout-logic-tuning.md).

The all-metric improvement objective remains unmet. Demo orders and real money
remain NO-GO; existing frozen target and runtime configuration unchanged.


### 6.1 Profit protection and entry-quality follow-up (2026-09-30)

Additional 48 research hypotheses (18 protection,30 entry quality),191 total
including earlier143. Break-even/candle-trail/runner activate only after a
closed bar shows >=0.5 initial risk in net executable profit; SL never widens.
BUY/SELL controls, candle body/close quality, and prior UTC calendar-day
direction tested. Prior-day guard uses bar-close date at midnight. All fixed
lot, cost-inclusive10% cap and daily40% admission controls retained.

Result remains **NO_QUALIFIED_STRATEGY**. Training SELL-only runner improves
net $330.00 versus baseline $302.64 and DD20.41% versus42.54%, but realized
RR0.832 versus1.189 and stressed net$290.12 versus$294.00 fail owner criteria.
No candidate validation or adoption. Full suite687 ran,685 passed,2 skipped.
Details and reproducible evidence: [follow-up](docs/reviews/2026-09-30-breakout-followup.md).


### 6.2 Central append-only strategy history (2026-09-30)

ประวัติกลาง: [Strategy Evolution / Change Log](docs/STRATEGY_EVOLUTION.md#central-strategy-change-log--2026-09-30).
บันทึกต่อท้ายด้วยID,from→trial,config snapshot,ช่วงข้อมูล,ผลbaseline/candidate,
และมติรับใช้. LOG-20260930-00แก้ข้อสรุปV3เก่า;LOG-01ถึง06เก็บการเปลี่ยนแปลง
และผลแต่ละรอบ. ข้อมูลเก่าคงไว้; correction/adoptionต้องเพิ่มรายการใหม่.
Research implementationหรือผลtrialไม่ได้หมายถึงเปลี่ยนcontractใช้งาน.

### 6.3 Adoption check (2026-09-30)

ตรวจผล loop ที่จบแล้ว 191 ชุดอีกครั้ง. ไม่มีชุดผ่านเกณฑ์กำไร, DD, realized RR และ cost stress พร้อมกัน. กริด Donchian/TP ที่กำไรเต็มช่วงสูงกว่าก็ยังมี tick DD เกิน 40% และ walk-forward ไม่ยืนยัน. **ไม่มีการรับ strategy ใหม่.** Contract ด้านบนคงเดิม. บันทึกต่อท้ายอยู่ที่ LOG-20260930-07 ใน [Strategy Evolution](docs/STRATEGY_EVOLUTION.md). ข้อความในข้อ 1–6.2 ไม่ถูกแทนที่.

### 6.4 Buy-pause trial (2026-09-30)

ทดลอง `buy_pause_drawdown=0.20` บน comparator Donchian 48 / TP 3. กฎเริ่มต้นยังเป็น `0` จึงไม่เปลี่ยน baseline. Training และ full path ไม่ผ่าน Strict Improvement เพราะ realized RR ลด และช่วง training กำไรกับ stress net แย่ลง. ช่วงที่รันยาว 184 วัน ไม่ใช่กราฟ 1 ปี. **ไม่มีการรับ strategy ใหม่.** รายละเอียดอยู่ที่ LOG-20260930-08 ใน [Strategy Evolution](docs/STRATEGY_EVOLUTION.md).

### 6.5 Climax-candle trial (2026-09-30)

ไม้ที่แพ้ของ comparator กองที่แท่งสัญญาณซึ่งเนื้อเทียนไปทาง breakout อย่างน้อย 80% ของช่วง high−low. ตัดไม้กลุ่มนั้นที่เส้น 0.80 แล้ว backtest ผ่านสี่แกนบนเทป 184 วัน แต่เส้น 0.75 และ 0.85 ไม่ผ่าน. **ไม่เขียนเข้า logic และไม่รับใช้.** รายละเอียดอยู่ที่ LOG-20260930-09 ใน [Strategy Evolution](docs/STRATEGY_EVOLUTION.md).

### 6.6 Bounded strategy campaign (2026-09-30)

Research-only campaign follows [frozen protocol](docs/specs/2026-09-30-strategy-campaign.md). Frozen target remains D30 / strict RSI30–70 / EMA50 / SL2.5ATR / TP6.25ATR; comparator remains D48 / no RSI or EMA / SL2.5ATR / TP3ATR. New experimental `Rules` support lower admission caps2.5/5/10%, daily limits5/10/20/40%, minimum breakout depths0/.15/.20/.25ATR, failed-breakout reversal within2 completed bars and either parent's fixed target. Default rules retain prior comparator behavior. Existing confirm, retest, failed-close, stagnant and trailing rules share one replay engine across both parents. Lot0.01 fixed; recovery absent; cap never exceeds10%.

Owner's new research gate supersedes strict RR improvement **for this campaign only**: net profit and WR higher, DD lower than both parents; DD<=20%, realized RR>=1; same requirements under common cost stress. Campaign <=384 unique candidates, batches<=48. Existing184-day tape is discovery only. New logic is not adopted or connected to live execution. Result/history appended after the actual run.

Actual campaign verdict: **NO_QUALIFIED_CANDIDATE**, 384 unique configs /8 batches, 0 passing all gates. No adoption. Evidence appended at [LOG-20260930-10](docs/STRATEGY_EVOLUTION.md) and [campaign report](docs/reviews/2026-09-30-strategy-campaign.md). Unseen validation, MQL5 parity and Demo remain blocked.

### 6.7 Structural invalidation follow-up (2026-09-30)

Owner requested continued strategy research. [New research protocol](docs/specs/2026-09-30-structural-strategy-campaign.md) replaces candidate SL2.5ATR with existing `stop_mode=structure`: BUY setup/trigger minimum low−tick; SELL maximum high+tick. Fixed0.01 lot, admission caps2.5/5/10%, daily limit5%, no recovery. Parent indicators and TP ATR distances retained; BUY/SELL/prior-day guards and closed-bar profit protection tested. **Frozen core and comparator baselines retain original ATR2.5 stops.** Exact384 candidates frozen before replay; first passing discovery candidate frozen by `--stop-on-pass`. No relaxation of profit, WR, DD<=20%, RR>=1 or cost-stress gates. No adoption or Demo qualification implied.

### 6.8 Retest + trigger stop + risk-distance TP follow-up (2026-09-30)

[New research contract](docs/specs/2026-09-30-risk-target-strategy-campaign.md): `stop_mode=trigger` uses confirming bar low−tick/high+tick, while `structure` retains setup+trigger extremes. `target_rr=1.5/2/3` sets TP from actual entry to initial rounded stop distance; `target_rr=0` preserves parent ATR target. Cost-inclusive admission still includes commission and adverse exit allowance; fixed0.01, cap2.5/5%, daily gate5%, no recovery. Nominal target RR never replaces realized net RR gate. Runner supports full-first short-circuit screening; skipped halves cannot qualify. Source snapshots preserve each campaign's exact code. Frozen core/comparator unaffected; no adoption.

### 6.9 Boundary/session/loss-circuit research (2026-10-01)

[New discovery protocol](docs/specs/2026-10-01-boundary-strategy-campaign.md): `stop_mode=boundary` uses frozen crossed Donchian edge−signed0.5ATR buffer, conservative tick rounding. `session_mode=london_ny` allows entries at UTC07–11 or12–17 only; all protective exits remain active. `cooldown_bars=0/1/4` starts after actual net losing exit; `max_daily_losses=0/1/2` counts exits in actual UTC exit day (0 disables count circuit). No clamp of lot/risk. Baseline defaults disable new gates and retain ATR SL. Tested cohort384 configs retains fixed0.01 and cap5/10%, daily admission loss gate5%. No adoption.

### 6.10 Wick-sweep research (2026-10-01)

[Separate logic family](docs/specs/2026-10-01-sweep-strategy-campaign.md): prior48 Donchian upper wick + close back below upper edge→SELL; lower wick + close back above lower edge→BUY; skip both-edge sweep candles. Completed-bar only; SL behind wick, optional risk-distance TP or3ATR, unchanged quote timing/cost-inclusive cap/fixed0.01/no recovery.384 predeclared configs; both frozen parents still comparison baselines. Full/half/stress metrics required for discovery pass; reused history cannot establish Demo readiness.

### 6.11 Trend-pullback research (2026-10-01)

[Separate research detection](docs/specs/2026-10-01-pullback-strategy-campaign.md): previous red candle + current close reclaim above prior high + above EMA50 with rising4-bar EMA50→BUY; inverse→SELL. Fixed EMA50 period, first50 bars warmup, completed M15, fresh quote only. Trigger stop/nominal risk-distance TP optional, fixed0.01/cap/no recovery unchanged.384 configs, no parent replacement.

### 6.12 Later profit-protection activation research (2026-10-01)

[Research protocol](docs/specs/2026-10-01-activation-strategy-campaign.md) adds `protect_after_r=1/1.5/2`; default remains0.5. Activation from closed-bar executable net versus initial cost-inclusive R; never widen stop, later quote only, runner removes TP only after valid stop update.288 predeclared configs; max384 per campaign; exhaustion derived from actual count. Existing core/baseline defaults unchanged; no adoption.

Actual follow-up verdict: six campaigns /2,208 additional configs,0 passing all discovery gates; `NO_QUALIFIED_CANDIDATE`. Goal not achieved. [Append-only research history](docs/STRATEGY_EVOLUTION.md), [consolidated results](docs/reviews/2026-10-01-strategy-continuation.md). No adoption; independent history,broker costs,parity/Shadow evidence still missing.


## 6.13 Public archive acquisition and drawdown admission research (2026-10-01)

Append-only research update; active frozen core remains unchanged and NO-GO.

Public Exness XAUUSDm monthly ZIPs Sep2024-Sep2025 acquired. Discovery Sep2024-Jun2025:49,581,644 audited Bid/Ask ticks,19,050 complete Bid M15 bars; Jul-Sep2025 remains ZIP-only sealed holdout, coverage not yet verified. Public indicative ticks do not establish target Demo execution parity; historical broker specs are assumptions. Activation288 on new discovery tape found0 qualifiers.

New research contract: risk_mode=drawdown_steps reduces cost-inclusive entry admission cap from configured10% to5% at equity DD>=10%, and2.5% at DD>=15%; restores on recovery, never exceeds configured cap. High-water mark includes all open-position tick equity. Fixed0.01 lot, isolated position, no recovery, protective exits continue.336 contracts defined before replay in docs/specs/2026-10-01-drawdown-admission-campaign.md. No DD guarantee or adoption claim.


## 6.14 Drawdown admission actual verdict (2026-10-01)

Four preserved public/admission runs:1,296 evaluations,0 qualifiers.336 new admission contracts; repeat datasets/screens are not new unique strategies. Strict protocol4 restores RR increase versus defined baselines; protocol3 kept separately. DD reduction alone did not satisfy combined profit/WR/RR/stress gates. No adoption; core remains NO-GO. [Detailed results](docs/reviews/2026-10-01-public-drawdown-results.md).


## 6.15 Owner DD25–30% research gate (2026-10-01)

Owner revised research DD ceiling: preferred<=25%, absolute<=30% including stress. Profit/WR/realizedRR must beat both defined baselines on identical data, full and halves. No capital/lot/cap/recovery changes; core remains frozen NO-GO. New protocol5 exposes --max-dd-pct30; default20 preserves previous gate. Re-screen is separate evidence, not rewriting old verdicts. All-tick positive observed equity does not guarantee future no-ruin. Actual broker costs and parity still unverified. See docs/specs/2026-10-01-dd30-requalification.md.


## 6.16 Risk-distance target catalog under DD30 (2026-10-01)

Research192 contracts: immediate parent breakout, original2.5ATR SL, TP1.5/2/3 times rounded initial entry-to-stop distance instead of ATR target; BE/trail at1/1.5R, daily10/20%, off/sell guard, resetfalse/true. Fixed0.01/risk10/no recovery unchanged. Spec docs/specs/2026-10-01-risk-multiple-dd30.md frozen before replay. No adoption or Demo readiness.


## 6.17 DD30 actual results (2026-10-01)

Activation288 + risk_multiple192 on2026 +192 on public discovery =672 evaluations,0qualified. Trial30 passesfull but failsfirsthalf profit/RR afterstress. HardDD30 alone did not satisfy jointbenefit criteria. Core remainsNO-GO; noadoption. [Append-only results](docs/reviews/2026-10-01-dd30-results.md).

## 6.18 Owner-authorized trial30 research Demo implementation (2026-10-01)

Owner explicitly selected `RESEARCH-D48-SELL-BE1R-20261001-T030` for actual MT5 Demo testing through Wine. This is a separate research-Demo trial, not adoption/profitability qualification of frozen D30 core and not real-money authorization. Earlier D30 NO-GO verdicts remain valid for that target.

Dedicated `scripts/ops/run_trial30_wine.py` → `scripts/ops/mt5_wine_trial30.py` → `scripts/trial30/runner.py` calls `scripts/strategy.py:trial30_bars`: prior48 Donchian SELL-only, ATR14 SMA, no RSI/EMA; canonical complete15/15 M1 Bid M15 UTC; first quote<=90s, current quote age<=60s; immediate market SELL fixed0.01. SL2.5ATR/TP3ATR; cost-inclusive admission<=10% actual broker equity, UTC daily20%. No recovery/partial/rollover liquidation. BE after subsequent closed M15 net executable profit>=initial cost-inclusive1R, cost-covered grid-rounded stop, never widen, preserve TP. Nominal TP/SL1.2 does not replace realized RR.

Admission reserves adverse entry and stop-exit slippage allowance0.10USD/oz each plus published Standard round-trip commission0 with account-bound reviewed24h attestation; spread already included in Bid/Ask. These are assumptions/source-backed tariff, not measured forward fill guarantees. Actual broker swap/commission/fee is reconciled in PnL; no swap-free entitlement claim and no overnight swap admission model. Requested/observed/fill prices logged separately; post-fill cap/spec violation closes owned ticket and halts.

Flat-midnight baseline reconstructs only from full reconciled deal cashflows and position volumes; held-at-midnight requires actual saved boundary equity. Deposits/unknown cashflows fail closed. Missing baseline blocks new risk but protective BE continues. Persistent single-writer journal claims intent before submission; UNKNOWN does not permit blind retry; confirmed broker events only. Demo/USD/hedging/exact identity verified before every mutation. Default Shadow; explicit execution flag plus Demo environment gate required.

Initial verification: fresh Wine identity200USD, no exposure, trade permissions enabled; actual Shadow WAIT/no_sell_signal. Detector parity12,100 reference bars, zero signal/ATR mismatches. No forward fill/BE proof yet; independent history/research qualification remains unpassed. [Operational contract and run commands](docs/ops/trial30-demo.md). Read implementation review/runtime evidence before claiming Demo lifecycle passed.

## 6.19 Two-sided challenger research (2026-10-01)

Owner requests BUY/SELL improvement while current Demo continues. Separate offline96-contract catalog in `scripts/research/bidirectional_campaign.py`: D48/ATR14, fixed0.01, SL2.5ATR, risk10%, daily20%, no recovery. BUY quality filters (off, EMA50/rising4bars, prior completed UTC up-day, dominant positive body, close upper20%, EMA+prior-day), both-side depth0/0.15ATR, TP3/6.25ATR, BE/cost-covered candle trail at1/1.5R. No runtime pin changes.

Owner confirmed each full/half base/stress must strictly beat trial30 net/WR/realizedRR, DD<=trial30 and<=30%, prove actual BUY and SELL, trades>=60/20. All6 scenarios evaluated and hashed; resume verifies protocol/input/source/artifacts. Trial30 second-half replay newly observed base+$73.916/DD32.931657%, stress+$12.167/DD33.337884%; original log entries preserved. Both exceed30%. A challenger cannot be selected from full-period alone. [Frozen research spec](docs/specs/2026-10-01-bidirectional-trial30-challenger.md). Discovery winner, independent validation and execution implementation are separate claims; if no qualified candidate, preserve running Demo contract.

Round1:96/0qualified. Round2 separately freezes96 alternate BUY-setup contracts: lower-wick rebound from prior48low or EMA50 rising4bar pullback above previous red-candle high; SELL D48 retained, conflict SELL precedence. Filters off/prior-day/body, signed setup-boundary depth0/0.15ATR; same TP/protection/risk/daily choices and all6 gates. SL remains2.5ATR; no structural substitution. Protocol2 and source snapshots separate from round1; no Demo contract modification or holdout tuning.

First two catalogs independently reverified all1164 scenarios, zero winner. Round3 freezes96 contracts using symmetric body_dominant/close_extreme/prior_day guards already implemented in replay, BUY breakout/lower_wick plus optional prior-day filter; same TP/protection, depth0 and risk/daily invariants. Purpose reduce false SELL as well as BUY triggers. No loosening performance gates. Frozen output `data/strategy_bidirectional_symmetric_trial30_campaign_2026_10_01`; runtime replacement remains conditional on verified winner.

## 6.20 Measured geometry/timing/exit tuning (2026-10-01)

Owner requests further implement/tuning with genuine measurements. Prior288 contracts had0qualified after1746 exact repeat scenario replays. New frozen288-contract loop (`--catalog tuning`),280 new +8 control repeats: stop atr/trigger/boundary and actual stop-distance reward1.5/2; delayed confirm/retest; failed-breakout0/1/2 completed-close and stagnant4bar exits; BE/trail activation0.5/1R. BUY breakout/lower-wick, prior-day filters, optional symmetric dominant-body guard. Existing replay math unchanged. Fixed0.01, cap10%, daily20%, no recovery/reset, UTC completedM15 remain. Structural/boundary stops only research; Demo trial30 SL2.5ATR remains pinned.

All6 scenario gates strictly compare net/WR/RR/DD/actual BUY+SELL with trial30. Protocol3 dynamic complete-catalog budget; no winner from incomplete prefix. Resume exact fullscenario repeat records actual verified_scenarios, FRESH_REPLAY_MATCH only when all baseline/evaluated results compared. Unmodeled BUY overnight swap, reused discovery and missing untouched/forward parity remain limits. [Frozen tuning spec](docs/specs/2026-10-01-bidirectional-geometry-tuning.md). No candidate success or runtime promotion asserted before measured results.

Geometry/timing/exit288 completed0qualified,1734repeat scenarios FRESH_REPLAY_MATCH;8control repeats all48artifacts BYTE_IDENTICAL with prior catalogs. Subsequent separately frozen96-contract admission cycle: BUY pause at2.5/5/10% all-tick peak drawdown; static/drawdown_steps cap (5% atDD10%,2.5% atDD15%); symmetric off/body guard, BE/trail1R, TP3/6.25ATR, BUY filter off/prior-day. Fixed0.01/SL2.5ATR/maxcap10/daily20 remain; actual fills both sides required, effective SELL-only fails. Existing replay logic reused, no new risk math. [Admission spec](docs/specs/2026-10-01-bidirectional-admission-tuning.md). Running trial30 contract unchanged; no improvement asserted before full/repeat validation.

Final measured verdict: admission96 also0qualified,582repeat scenarios FRESH_REPLAY_MATCH. Current task384 evaluations/376new+8controls,2316exact repeated comparisons, no runtime promotion. Highest admission fullstress net+$792.447 hasDD33.643765%/WR32.857143%, secondhalfbaseDD58.492423%, so rejected despite larger fullprofit. [Verified continuation report](docs/reviews/2026-10-01-tuning-continuation-results.md). Research loops ended; owner-authorized Demo watcher continues independently.

### 6.21 Direction-specific horizon research (2026-10-01)

Research only: [frozen hypothesis](docs/specs/2026-10-01-bidirectional-horizons.md) tests independent BUY/SELL prior-channel horizons12/24/48/96, optional direction-aligned completed-bar EMA50/200 and four-bar slope. ATR14/SL2.5ATR/fixed0.01/risk10%/daily20% preserved; TP3/6.25ATR and BE/trail1/1.5R. No calendar/outcome switching. 384 registered contracts include8 D48 no-trend controls. Same six strict trial30 comparisons; discovery does not authorize runtime replacement. Actual Demo remains SELL-only trial30. Results pending; no superior performance claimed.

Horizon continuation: [candle-quality128](docs/specs/2026-10-01-bidirectional-horizon-quality.md), independent12/24/48/96 BUY/SELL channels, symmetric body>=half-range or close within directional outer quarter, TP3ATR, BE/trail1/1.5R. EMA off; other risk/stop constraints unchanged. Includes8 D48 controls; research only, results pending.

Compression continuation: [216 prior-range contracts](docs/specs/2026-10-01-bidirectional-compression.md), directional24/48/96 ranges divided by prior ATR14, maximum6/9/12 inclusive; EMAoff/50, guardoff/body, BE/trail1R, TP3ATR. Current breakout ATR cannot widen the compression threshold. Fixed lot/risk/stop unchanged. Research-only; six original gates and no automatic Demo promotion.

RSI reversal continuation: [72 rolling-RSI contracts](docs/specs/2026-10-01-bidirectional-rsi-reversal.md). RSI simple rolling gain/loss7/14/21, lower25/30/35 and symmetric upper; BUY recross upward plus positive close change, SELL recross downward plus negative close change. EMAoff/50, body guardoff/on, BE/trail1R, TP3ATR. Full warmup, flat RSI50; trigger close recorded as anchor. Not Wilder RSI or original B1 guard. Original fixed lot/risk/ATR stop and six gates unchanged; research-only.

Direction-specific continuation: [144 RSI/D48 contracts](docs/specs/2026-10-01-bidirectional-hybrid-oscillator.md). One fixed side uses rolling-RSI price reversal, opposite side retains unfiltered D48; parent wins simultaneous conflict and retains channel anchor. RSI trend applies only to RSI side. Same risk/ATRstop2.5/TP3 and six original gates, BE/trail1/1.5R. Single position only; the word hybrid here denotes entry signals, never recovery baskets. Research-only, not Demo adoption.

RSI BUY admission continuation2026-10-02: [108 frozen contracts](docs/specs/2026-10-02-bidirectional-hybrid-admission.md), RSI7/14/21 threshold25/30/35 EMAoff/50, pause BUY at account peak-equity DD2.5/5/10%; SELL unfiltered D48, BE/trail1R. Fixed lot/risk/stop/target and six gates unchanged; research only, results pending.

Setup-invalidation continuation2026-10-02: [108 new RSI BUY/D48 SELL contracts](docs/specs/2026-10-02-bidirectional-hybrid-invalidation.md) with BUYpause5/10% and EMA50; one failed held-bar close across setup anchor and/or four stagnant held bars with net<=0 cause first-post-close quote exit. RSI anchor trigger close, SELL anchor crossed D48 level; exit applies both sides. No entry-bar holding count, resizing or widened stops. Other parameters/six gates unchanged; research only.

Measured continuation outcome: [2026-10-02 report](docs/reviews/2026-10-02-research-continuation.md), seven cycles1,160 evaluations/1,144 new versus preceding five catalogs/16 controls,0 qualified. All7,002 whole-result repeats match. Admission22 improves full net/WR/DD but RR~1.10 and secondhalfDD32.81/35.79 fail; never promoted. Research model omits swap; no untouched validation. Running Demo still trial30 SELL-only; fresh identity/tariff review renewed unchanged cost assumptions2026-10-02.

## 6.22 Rounded-stop reward research (2026-10-02)

[Preregistered594 contracts](docs/specs/2026-10-02-bidirectional-hybrid-reward.md): RSI BUY7/14/21 threshold25/30/35 EMA50, SELL D48, BUYpause2.5/5/10%, nominal target1.25/1.35/1.5/2 times actual rounded initial stop distance. BE/trail at0.5/1R; target2 additionally1.5R; protectionoff one state. Inactive activation>=target omitted. ATR14/SL2.5ATR/fixed0.01/maxcap10/daily20 remain. Research enum now admits1.25/1.35; price/risk/fee/protection formulas unchanged, original trial30 target3ATR retained. Six strict gates, actual Bid/Ask provenance and exact repeat required; no Demo promotion, swap still unmodeled. Final594/0qualified,3,570 exact fresh repeat scenarios.

Rounded-reward session continuation: [108 preregistered contracts](docs/specs/2026-10-02-bidirectional-reward-session.md), sameRSI BUY/D48 SELL, pause5/10%, target1.35/1.5R, off/BE/trail1R, reject BOTH entry directions when completed M15 close hour>=21UTC. Midnight allowed; every OHLC/tick still processed for held-position exits/protection. This is a fixed research entry filter, not actual broker swap calendar or overnight liquidation. Other risk parameters/six gates remain. Baseline all-session trial30 unchanged; final108/0qualified,654 exact fresh repeat scenarios.

### 6.23 Rounded reward loss-cluster admission (2026-10-03)

[324 frozen contracts](docs/specs/2026-10-03-bidirectional-reward-admission.md): RSI BUY7/25,30,35/EMA50 + D48SELL, BUYpause5%, target1.35 rounded-stop R, protectionoff. Staticcap10/5% or drawdown_steps10%, daily10/20%, cooldown0/1/4 bars from losing exit tick, UTC daily total losing-trade limit0/1/2, entry_sessionall/avoid_rollover. Existing replay unchanged; fixed0.01/max10/no recovery. Hypothesis motivated by reward156 passing six profit/WR/RR comparisons but failing four DD gates; no qualification assertion. All six original gates and exact repeat required; final324/0qualified,1,950 exact repeat scenarios; Demo trial30 unchanged.

### 6.24 Rounded reward symmetric quality (2026-10-03)

[108 frozen contracts](docs/specs/2026-10-03-bidirectional-reward-quality.md): RSI BUY7/25,30,35/EMA50 + D48SELL, BUYpause2.5/5/10%, nominal rounded-stop target1.35/1.5R, protectionoff. Existing symmetric body_dominant/close_extreme/prior_day guards, all/avoid_rollover entry sessions. No replay math change; fixed0.01/SL2.5ATR/max10/daily20/no recovery. Hypothesis filter false entries behind persistent DD failures; original six gates, actual both sides and exact fresh repeat required. Final108/0qualified,654 exact repeat scenarios; running Demo unchanged.

### 6.25 RSI/D48 rounded-reward geometry (2026-10-03)

[216 frozen contracts](docs/specs/2026-10-03-bidirectional-reward-geometry.md): RSI BUY7/25,30,35/EMA50 + D48SELL, BUYpause2.5/5/10%, nominal target1.35/1.5/2R from rounded stop. Existing trigger(low/high +/-tick) or boundary(recorded anchor minus direction*0.5ATR) stops; RSI BUY anchor trigger close, SELL prior48low. Protectionoff/trail1R, all/avoid_rollover. Cost-inclusive protection activation differs from geometric targetR. Risk/lot/daily unchanged; no new engine math, no Demo SL change. Admission324 and quality1080qualified; this hypothesis tests initial loss geometry. All six strict gates/exact repeat required; final216/0qualified,1,302 exact repeat scenarios.

Reward continuation final: five cycles1,350 evaluations/1,344 new scoped contracts+6 equivalent controls,0qualified,8,130 exact full-result repeats. [Measured report](docs/reviews/2026-10-03-reward-research.md). Reward156 improves all six net/WR/RR but fails four DD comparisons; not promoted. Research swap omitted/untouched validation absent. Wine read-only auditOct3 proves current quote_stale before signal, historical4SELL detections and zero trial30-magic orders in retrieved window; prior missed-entry guard traces incomplete. Runtime SELL-only trial30 unchanged; no forced order or cap removal.

### 6.26 Configurable ATR-stop research (2026-10-03)

Research `Rules.stop_atr` now supports1.5/2.0/2.5, default2.5 preserves existing behavior; only `stop_mode=atr` consumes it. Structural/trigger/boundary stops unchanged. TargetRR still derives actual rounded stop distance; slippage/commission and10% risk gate unchanged. Fixed0.01; smaller stop never bypasses executable-side geometry or risk checks. Hypothesis: intermediate ATR stops can reduce risk versus2.5 without aggressive trigger/boundary stops rejected previously. Runtime trial30 remains explicit2.5ATR SELL-only; no config promotion. Public replay tests prove literal BUY/SELL stop+target and fixed-risk admission; completed campaign verdicts below.

ATR-stop continuation [432 preregistered settings](docs/specs/2026-10-03-bidirectional-atr-stop.md): RSI BUY7/25,30,35/EMA50+D48SELL, BUYpause2.5/5/10%, SL1.5/2ATR, nominal target1.35/1.5/2R, off/trail1R, daily10/20%, UTCdaily loss-count0/1. Default baselineSL2.5 preserved. Staticcap10/fixed0.01/all-session/no recovery; six strict original gates and exact fresh repeat remain mandatory. Same raw tick dataset, no sealed holdout or Demo promotion. Source/rule schema changes serialized stop_atr metadata; unchanged baseline full results must match apart from rule metadata.

Research oscillator BUY contracts optionally accept `parent_lookback=24/48/96`: SELL channel becomes prior rolling low of that many complete M15 bars, shifted1; retained SELL wins conflict and retains its own channel anchor. No RSI BUY anchor/trend change. RSI BUY may warm up independently because both its ATR-trade anchors use trigger close; SELL waits full parent window. Omitted parent_lookback preserves existing D48 behavior, explicit48 controls require full-result parity. No Demo horizon change.

Directional parent continuation [192 registered settings](docs/specs/2026-10-03-bidirectional-parent-horizon.md): RSI BUY7/30,35/EMA50 + SELL prior-low24/48/96, pauseBUY5/10%, ATRSL2/2.5, rounded-stop target1.35/1.5R/off, daily10/20%, UTCdaily total losing-trade limit0/1. D48 controls alias-normalized to existing parent behavior; exact complete-result match required apart from rule metadata. Fixed0.01/cap10/all-session/six original gates unchanged; research only, no runtime replacement.

`stop_atr` appended to Rules constructor fields so existing positional arguments retain meanings; kwargs-based frozen campaign rules/math unaffected. Compatibility regression reproduced and fixed before commit. ATR432 complete0qualified,2,598 exact repeats. Parent verifier explicitly loads hashed frozen engine/main so source-order compatibility fixes do not mix engines with frozen research.

Review caught SELL24 hidden D48 warmup: changing only ll left hhNaN before48, and replay validates both anchors. Natural-OHLC public replay reproduced0trades where24 should admit. Fix recomputes both prior high/low using selected parent horizon, shift1; RSI anchors remain trigger close. First parent192 snapshot superseded for qualification; retain hashed raw artifacts, rerun192 under corrected source. ATR432 unaffected.

SELL-parent trend research: optional `parent_trend_span=0/50/200` requires explicit parent horizon. Nonzero allows SELL only after close<EMA and EMA<EMA4barsago, using complete-bar close and full EMA warmup. Filter applies only parent SELL; RSI BUY keeps its own EMA50 alignment/warmup and anchors. Zero/omitted preserves corrected parent behavior; no runtime change. Hypothesis reduce countertrend SELL behind D24 second-half DD39.96/43.28 despite full/first-half strict passes.

Parent trend continuation [288 settings](docs/specs/2026-10-03-bidirectional-parent-trend.md): RSI BUY7/30,35/EMA50 + SELLprior-low24/48/96 with parentEMAoff/50/200, BUYpause5/10%, ATRSL2.5/nominalR1.35/1.5/off, daily10/20%, UTCdaily loss-count0/1. EMA200 SELL waits full EMA and four-bar slope availability; RSI BUY independent. Trendoff96 controls vs corrected prior192; original six gates/fixed0.01/cap10 remain. Research only, no Demo change or future-profit assertion.

Bearish D24 quality continuation [24 preregistered configs](docs/specs/2026-10-03-bidirectional-parent-quality.md): sameRSI BUY7/30,35/EMA50, pause5/10%, SELLprior-low24/EMA50, target1.35/1.5R/off, daily10%/1losing trade; existing symmetric body_dominant/close_extreme/prior_day guard applies both directions. No new signal/risk math, fixed0.01/SL2.5ATR/maxcap10/all-session/no recovery, six original gates and fresh whole-result repeats retained. Motivated by measured partial trend prefix, not a qualified or independent winner. Runtime unchanged.

Bearish D96 intermediate-reward [48 preregistered configs](docs/specs/2026-10-03-bidirectional-parent-reward-fine.md): RSI BUY7/30,35/EMA50, pause5/10%, SELLprior-low96/EMA200, rounded-stop target1.40/1.45R/off, daily10/20%, losing-trade count0/1/2. Research target_rr enum additionally accepts1.4/1.45; target/risk/protection math unchanged. Fixed0.01/SL2.5ATR/maxcap10 and original six gates retained. Prefix137 motivates closer RR/DD trade-off, not qualified/independent success. Earlier campaigns continue exact original hashed engine/main; no Demo target change.

D96 tighter BUY-pause [12 preregistered configs](docs/specs/2026-10-03-bidirectional-parent-reward-pause.md): same RSI7/30,35/EMA50 + SELL96/EMA200, target1.40/1.45R/off, daily10%/losing-trade count0/1/2, peak-equity BUYpause2.5% instead of5/10. Six fine48 settings pass second-half paired gates but none all windows, motivating earlier BUY admission suppression. Existing replay/risk unchanged; fixed0.01/max10% and original gates/fresh frozen repeats retained. No calendar/outcome switching or runtime promotion.

Config continuation final: ten valid campaigns1,284 evaluations/1,141 new scoped contracts+143 equivalent controls,0jointly qualified;7,764 exact fresh whole-result repeats. All60 baseline cases match pinned prior results except rule metadata; controls match complete parsed outcomes. Initial parent192 superseded for anchor-warmup implementation mismatch, excluded from counts/qualification; corrected192 rerun. NewD24 trial106 improves full/first-half net/WR/RR/DD but second-halfDD39.96/43.28 fails. D96 rewardfine31 passes second-half paired gates but fullstress-15.214/DD37.31 fails; tighter BUYpause12 produces2second-half passes/0joint. [Measured report](docs/reviews/2026-10-03-setting-tuning.md), [hashed index](docs/reviews/2026-10-03-setting-tuning-index.json). Swap omitted/discovery reused/untouched validation absent. Ten loops finished, original Demo unchanged; current persistedstatus execute=true/quote_stale blocks before signals. No indefinite worker, profitability/broker parity or forced-order claim.

Risk-admission continuation [36 preregistered configs](docs/specs/2026-10-03-bidirectional-parent-risk.md): RSI7BUY/lower35/EMA50/pause5%, parentSELL24/trendoff/target1.35R or SELL96/EMA200/target1.45R, staticcap5% or drawdown_steps max10%, cooldown0/1/4bars, UTC losing-trade count0/1/2, daily10%/off/SL2.5ATR. Existing admission math rejects over-cap fixed0.01; no sizing or window switching. Six gates/fresh frozen repeats retained, research-only/no Demo change. Risk36 completed0qualified/0paired-window passes,222 exact fresh repeats; max fullstressnet13.448 and some cases admit one trade, failing profit/trade-count gates.

D96/EMA200 intermediate-ATR [72 preregistered configs](docs/specs/2026-10-03-bidirectional-parent-atr.md): RSI BUY7/lower30,35/EMA50/pause5/10%, SELL96/EMA200, SL1.5/2ATR, rounded-stop target1.35/1.45/1.5R/off/daily10%/losing-trade count0/1/2. Existing formulas/staticcap10/fixed0.01 and six original gates preserved; shorter stops do not bypass geometry/risk. Hypothesis motivated by risk36 low admission and D96 partial passes; no Demo change/independent-winner claim. Completed72/0qualified/0paired passes,438 exact fresh repeats; maxfullstressnet80.736/DD43.05 fails.

D24 early-protection [144 preregistered configs](docs/specs/2026-10-03-bidirectional-parent-protection.md): RSI BUY7/lower30,35/EMA50/pause5/10%, SELL24/parentEMAoff,50, SL2.5ATR/rounded-stop target1.35/1.40/1.45R, break_even0.5R or candle_trail0.5/1R, daily10%/losing-trade count0/1. Existing cost-inclusive protection activation/math retained; fixed0.01/staticcap10/all-session and original six gates/fresh frozen repeats remain. D24 partial windows motivate protection hypothesis, no Demo change. Completed144/0qualified/0paired passes,870 exact fresh repeats.

Bearish D48 setup-invalidation [36 preregistered configs](docs/specs/2026-10-03-bidirectional-parent-invalidation.md): retain measured parent-trend178 RSI BUY7/lower35/EMA50/pause5%, SELL48/EMA50, target1.35/1.40/1.45R/off, cooldown0/1/4bars, failedheldclose0/1 or stagnant0/4heldbars net<=0, daily10%/losing-trade limit1/SL2.5ATR/fixed0.01/staticcap10. Uses existing replay formulas/anchors/causal exits; first combination expected control178, no novelty claim before audit. Full/first paired passes motivate second-half DD research, original six gates/fresh repeat unchanged; no runtime promotion. Completed36/35new+1control,0qualified,222 exact fresh repeats;3full/6first-half paired passes,0second-half. Control1 matches trend178 complete outcomes.

Further runtime audit06:28:46UTC: persisted execute=true/quote_stale and active/halt null; local stored cost policy expired06:09:10UTC Oct3 and validatesinvalid_or_stale even against own storedfingerprint. Fresh livebinding/tariff review not performed; no timestamp-only refresh. This further admission prerequisite is distinct from currentquote blocker.

### 6.27 Annual archive qualification research (2026-10-03)

Owner adds one-year requirement. [Frozen annual spec](docs/specs/2026-10-03-annual-bidirectional.md): actual public XAUUSDm Oct2025–Sep2026,365days/12months/104,133,248 Bid/Ask ticks/23,230 complete UTCM15. Annual CLI `--require-calendar-year` rejects short/unordered/missing/empty months or actual tick/bar count mismatch before scenarios; requirement enters protocol and resume. No change to default six-month comparator or Demo settings. Existing sealed Jul–Sep2025 untouched; annual2026 overlap remains reused discovery.

Repeat existing parent invalidation36/rewardfine48/ATR72 on annual baseline/full/two independently reset halves. Add research-only symmetric trend breakout36: BUY+SELL Donchian24/48/96 with EMA50/200 and four-bar slope, rounded-stop target1.35/1.5/2R, protectionoff/BE1R, SL2.5ATR/fixed0.01/staticcap10/daily10%/one UTC losing trade/day/no BUY drawdown pause. Existing formulas and gates unchanged. No recovery, date-based setting selection or runtime promotion.

Annual trial30 full/first-half:7 losing SELLs, realizedRR=None. Initial strict qualifier rejected undefined baseline RR before owner approval recorded below. Raw-quote independent ledger/DD checks confirm baseline/control arithmetic, not superiority or broker parity. Initial annual performance evaluation was pending at that stage; coverage/unit fixtures alone never establish superiority.

Annual outcome: [192 completed evaluations](docs/reviews/2026-10-03-annual-tuning.md),0qualified;1,176 exact fresh whole-result scenario repeats and30 independent raw-quote ledger/DD checks. Every candidate exceeds30% fullbaseDD. Highestbaseprofit symmetric17 net1,057.245/DD46.5045, stress51.309/DD65.6278; noteligible. One real annualBE default mismatch0.5vsdeclared1.0 fixed explicitly; initial10results preservedsuperseded, corrected36fullyrerun/repeated. At that initial stage undefined annualbaselineRR stayed failclosed; subsequent owner-approved RR policy recorded below also yields0joint qualifiers for those192. All finite workersfinished; no superior BUY/SELL result or Demo promotion.

Owner later approved annualall-lossRRreference0, with strategyRR>1 unchanged. Qualifier uses actual ledger-derived `loss_trades == trades >0`, winrate0/netnegative; measuredbaselineRR staysNone. Empty/mixed/breakeven/allwinning unknown ratios stillreject. New protocols pin policy; original192 frozen artifacts/proofs preserved and separately requalified. Existing finiteRR baseline behavior unchanged.

Next [annualresearch loops](docs/specs/2026-10-03-annual-bidirectional.md): annual_risk36 symmetricDonchian24/48/96 EMA50/200 reward1.35/1.5/2, staticcap5% or drawdown_stepsmax10%; annual_confirmation48 samehorizons/trends reward1.25/1.35, ATRSL1.5/2.5, causalconfirm/retest entries. Both off/daily10%/oneUTCdaily losingtrade/noBUYpause/fixed0.01/no recovery, all six gates and full-year datasetunchanged. Researchonly; no qualified winner or Demo change before evidence.

Annual hybridunpaused96 [spec](docs/specs/2026-10-03-annual-bidirectional.md): RSI BUY7/lower25,35/EMA50 + parentSELL24/48/96 EMA50/200, ATRSL1.5/2, rounded-stop target1.25/1.35R, static10 or drawdown_stepsmax10, BUYpauseoff/protectionoff/explicitinactive1R/daily10%/oneUTC loss/fixed0.01. Hypothesis connects earlier annualhybrid limitedBUY count with pause suppression; formulas/causalanchors/approvedRRpolicy/sixgates unchanged. Frozen96 researchonly; no profitability or runtime claim before all measured evidence.

AnnualUTCsession research36 [spec](docs/specs/2026-10-03-annual-bidirectional.md): D48EMA50 symmetricbreakout or RSI7BUY35EMA50 + D48EMA50SELL, completedbarUTC windows[00,07)/[07,13)/[13,20), ATRSL1.5/2.5 RR1.25/1.35/2, immediate/off/explicitinactive1R/daily10%/oneUTC loss/noBUYpause/staticcap10/fixed0.01. Public signaltransform adds exactUTC-aware completedboundary masks forbothsides; invalid local/naive datesreject. Newhourcontracts immediateonly, no future/date-based logic. ApprovedRRpolicy/full365day/sixgates/no recovery/noDemochange retained; researchhypothesisonly.


`annual_directional`48 preregistered: RSI BUY7/14, lower25/35, EMA50 causal slope; SELL prior-low48 without trend filter. SELL exits retain trial30 SL2.5ATR/TP3ATR/BE1R. BUY uses independent SL1.5/2/2.5ATR and rounded-stop target1.25/1.35/1.5/2R, protectionoff. Product2*2*3*4=48. Common fixed0.01/staticcap10/daily20%, no BUYpause, no daily loss-count restriction. New optional research `Rules.buy_stop_atr`, `buy_target_rr`, `buy_protect_mode` defaultNone/inherit; appended fields preserve positional compatibility. ATR-only overrides reject incompatible stop modes; shared quote/cost/rounding/risk formulas unchanged. Public replay tests verify both actual sides, SELL BE lifecycle parity and cost-inclusive overcap rejection. Hypothesis: earlier shared short exits reduced profitable SELL second-half behavior. It is disproved if this directional catalog still fails joint gates. No date selection, recovery or Demo/runtime change; annual/halves/base/stress and approved RR rule retained.


`annual_directional_trend`48 preregistered follow-up: RSI BUY7/lower35/EMA50, BUY SL1.5/2ATR and target1.25/1.35R/off; SELL prior-low24/48/96 with EMA50/200 and four-bar slope, SELL SL2.5ATR/TP3ATR/BE1R. Common static10% or drawdown_steps maximum10%, fixed0.01/daily20%/noBUYpause/noUTC losing-trade-count restriction. Product3*2*2*2*2=48. Initial unfiltered directional entries show high measured DD; hypothesis tests whether causal SELL trend filtering and conservative admission remove that countertrend failure. Frozen original directional48 contract remains identical. All six gates/annual inputs/approved RR policy unchanged; neither reduced trade count nor profits alone qualifies. Research-only, no Demo switch.


`annual_directional_circuit`24 preregistered: two BUY profiles RSI7/lower35/EMA50 and RSI14/lower25/EMA50; BUY SL1.5ATR, rounded-stop target1.35/2R/off; SELL prior-low24/48/96 EMA50/200, SELL SL2.5ATR/TP3ATR/BE1R. Staticmax10/fixed0.01/daily10%/one losing trade per UTCday/noBUYpause. Product2*3*2*2=24. Motivated by actual unpaused28 full/first paired pass and directional28 second profit/DD improvement but WR failure, plus directional static full highDD and drawdown_steps low admission. Tests whether daily circuit contains losses while preserving more admission than reduced drawdown cap. All settings predeclared, no calendar switching or criterion relaxation; annual/halves/base/stress/approvedRR definition unchanged. Existing math only, no Demo modification.


`annual_directional_fine`24 preregistered from measured full-window passes circuit22/24: RSI BUY14/lower25/30/35/EMA50; BUY SL1.0/1.5ATR and rounded-stop target1.5/2R/off; SELL prior-low96 EMA50/200, SELL SL2.5ATR/TP3ATR/BE1R. Static10/fixed0.01/daily10%/one UTC loss/noBUYpause. Product3*2*2*2=24. BUY-only optional ATR override permits1.0 via public replay RED→GREEN geometry/admission test; shared/SELL allowed multipliers unchanged, costs-inclusive cap still rejects. Motivation: circuit22 first-half157signals but138risk rejects and12trades; extra shorter-cost-admissible BUY entries may clear20trade minimum and improve halfstress profit without increasing cap. Target/cost/DD consequences remain measured, not presumed. Circuit22/24 exact controls included when threshold25/stop1.5/BUY2R; all previous frozen contracts/outcomes preserved. Annual six-scenario gates and approved RR rule unchanged. No runtime deployment or profitability claim.


Annual replay performance implementation (2026-10-03): actual frozen annual profiling identified full-window quote-copy/validation allocations and scalar23,230bar searches. Zero-extra-spread floating Bid/Ask use immutable input views; nonzero stress spread and non-floating inputs retain original arithmetic. Validation processes100k chunks with one timestamp overlap, rejects all original invalid/crossed/unsorted cases. Completedbar UTC epochms indices computed in one vector search, preserving first duplicate quote and end-exclusive windows. No held-tick chunks/ledger checkpoint compression/SL/TP/fees/risk/admission strategy formula changed. Optional BUY1.0ATR research support documented above remains separate. Whole-result parity and measured speed/memory required before performance claim; old frozen sources preserved. Async used only for bounded worker/verifier subprocess lifecycle, cancellation/timeout reaps children and propagates failures; CPU replay remains synchronous isolated process, no async MT5/runtime migration.


`annual_fast_quality`72 preregistered after measured full/first-vs-second tradeoff: symmetric prior-bar Donchian12/24/48 with EMA50/200 causal four-bar slope; completed candle guardoff/body_dominant/close_extreme, immediate/causalconfirm, commonSL1.5ATR/rounded-stop target1.35/1.5R/off/explicitinactive1R/static10/fixed0.01/daily10%/oneUTC losing trade/noBUYpause. Product3*2*3*2*2=72. Existing causal signal/entry/guard/risk formulas only; no async replay math or runtime changes. Hypothesis: faster quality-filtered breakout increases admissible both-side participation and reduces false-breakout losses relative to sparse oscillator setups. Annual six gates, approvedRRpolicy, full365days and independently reset halves unchanged. Discovery remains adaptive/reused; configs include possible existing equivalent controls, so evaluations are not independent/unique strategy experiments. Frozen before results and repeated in full.


`annual_short_sell`24 preregistered: BUY RSI7/lower35 or RSI14/lower25 with EMA50; BUY SL1.5ATR/rounded-stop target1.35/2R/protectionoff. SELL prior-low48/96/EMA200, shared SELL SL1.5ATR/TP3ATR, protectionoff or cost-inclusive BE0.5/1R. Fixed0.01/staticcap10/daily10%/oneUTC losingtrade/noBUYpause. Product2*2*2*3=24. Measured unpaused28 passes full/first but fails second profit with short shared reward, while directional baselineSELL long stops reduce first-half admission. Hypothesis: shorter SELL cost-risk geometry keeps BUY admission path, but retains larger3ATR SELL reward and tests earlier protection. Existing enums/formulas only; all six annual gates/approvedRRpolicy unchanged, no recovery or runtime promotion. Explicit0.5R is intentional new experiment, distinct from prior declared1R-default defect.


Annual research checkpoint final:14completedcatalogs648parameter evaluations,0joint qualifiers,3,972exact frozen whole-result repeats; additional optimizedcontrol24 adds0settings/150freshrepeats/150exactcross-version matches. Independent samefeed rawquote arithmetic90scenario evaluations match, not broker/signal oracle. Directionalcircuit22 annualbase533.916/DD24.49% andstress512.056/DD24.72% passfull; first12trades<20/net-12.561/-13.083 andsecondstress429.542<baseline452.366fail. Fine6 passsecond butfullDD37.44/33.18 andfirst12fail. Approvedall-lossRRdefinition/othergates preserved; no winner or Demo promotion. [Final report](docs/reviews/2026-10-03-annual-tuning.md), [hashed results](docs/reviews/2026-10-03-annual-final-results.json), [profile/paired performance](docs/reviews/2026-10-03-replay-performance.md). Pairedreplay1.43–6.15xspeedup with unchanged whole results; baseallocationpeak2486→9–10MiB, stress1599MiB, not residentRAM claim. Boundedasyncv2waitallsnapshotSHA fixes observedreadinessrace; timeout/error cleanup and actualtwochildexit0. Fullsuite776/774pass2skip; finite workerscomplete. Requested superiorstrategy remainsunmet, actualDemoselection unchangedtrial30SELLonly.

### 6.28 Current-equity research sizing and profit_dd_v2 (2026-10-03)

Behavior-preserving research module separation and bounded subprocess supervision:
[refactor evidence](docs/reviews/2026-10-03-research-refactor.md). Public campaign/replay
APIs remain compatible; new transitive implementation modules are source-hashed,
so prior frozen campaigns/caches require their original sources or a fresh output.
M5 preparation optimization preserves completed-bar causality, strict equality,
UTC management and risk/admission math. Trial30 Demo contract remains unchanged.

Owner authorizes research-only risk budgets through20%, current-equity lot sizing,
and USD200 initial balance for each independent window with compounding/no top-ups.
Demo trial30 remains fixed0.01/cap10%. New qualification policy `profit_dd_v2`
requires positive net above trial30 and DD<=trial30/30% in all six annual scenarios,
60full/20half trades and actual both-side fills. WR/RR reported without superiority
or RR>1 gates. `strict_v1` preserved; older results never relabeled.

[Stage1 spec](docs/specs/2026-10-03-equity-sizing.md):60 frozen variants across fine7,
circuit22 and unpaused28 ×10 budgets ×fixed/risk sizing. Risk sizing floors to
broker step and rejects below minimum or above cost-inclusive budget; every held
position uses its volume for PnL/fees/BE/margin/cost attribution. Costs still commission0
assumed/no swap in this experiment; COST_INCONCLUSIVE, no final qualification or
runtime promotion. Actual full-year replay/fresh-repeat results pending.

Stage1 completed60/0qualifiers with366 exact fresh full-result replays. Increased
cap worsens DD, dynamic sizing alone does not solve qualification. Follow-up
`annual_short_buy`32 predeclared in stage1 spec: RSI7/14 cross25/35EMA50 with
BUY stop0.5/0.75ATR/TP2/3R/off or BE1R; SELL96EMA200 SL2.5ATR/TP3ATR/BE1R,
fixed0.01/static10/daily10/one UTC loss. Optional BUY overrides expanded only;
legacy/shared SELL multipliers unchanged. New-policy verdict explicitly records
COST_INCONCLUSIVE for commission0 assumption and omitted swap, even if statistical
discovery gates pass. No Demo change.

Stage2 shortBUY32 completed0qualifiers/198fresh exact replays. Stage3 research-only
M15/M5 causal retest128 variants (two64 intraday/bounded24 catalogs), specified in
[research spec](docs/specs/2026-10-03-equity-sizing.md). Replay optional `entry_frame`
uses completedM5 triggers, Bid-extreme one-tick stops with SELL Ask-spread conversion;
BE management remains completedM15. Fixed0.01/cap10 controls. Intraday cutoff20:30UTC,
first-quote flatten20:45UTC; bounded24 first-quote exit after24h. Legacy defaults retain
holding_mode=legacy. No swap accrual/reserve implemented; COST_INCONCLUSIVE, no Demo
promotion. Missing M1 prevents completeM5; pending TTL2/4 counts complete bars,
opposite setup replaces, wrong-side close invalidates; all chronology awareUTC.

M5 review fixed two public replay regressions: neutral boundary equality now keeps
pending through remaining TTL; prior-day mapping uses M5+5/M15+15, preventing a
future midnight bar from influencing prior_day guard. Both RED->GREEN exercised
actual replay seam. Initial stage3 two64 artifacts preserved SUPERSEDED, corrected
128 source-pinned campaigns and fresh whole-result repeats required. Review source
[post-mortem](docs/post-mortem/2026-10-03-m5-retest-debug.md).

Corrected stage3:128/0qualifiers,780 exact fresh whole-result replays, two bounded
async repeat child exits0/0. Stage4 research `annual_m5_hybrid`64: BUY D24/48 EMA50
M5retouchTTL2/4 triggerlow one-tick stop/TP1.5/2R/off or BE1R, SELL D48/96EMA200
immediate completedM15/SL2.5ATR/TP3ATR/BE1R. Optional BUY stop override preserves
shared SELL ATR. SELL priority cancels pending BUY; common intraday/bounded24,
fixed0.01/static10/daily10/oneUTC loss. Public M5 replay records side/reason/UTC
rejections for funnel audit. Cost validation and independent holdout still pending;
no live adapter or Demo settings changed. Stage4 outcomes pending.

Stage4 hybrid64 completed0qualifiers/390fresh exact replays. Stage5
`annual_m5_hybrid_quality`48 preregistered: seeds14/15 ×riskcap5/7.5/10 ×SELLstop2/2.5
×SELLguardoff/body_dominant ×BUYTP2/3R. SELL bearish completed body>=half positive
range, BUY unchanged; other seededrules intact. Public candidate_frame optional
SELL filter defaults off. M5 cache key includes filter; both horizons/TTL and
mode remain pinned. Source replay search results explicitly arrays for strict
scoped typechecking; no quote arithmetic or tick omission. Outcome pending;
COST_INCONCLUSIVE/noDemochange remains.

Stage5 quality48 completed0qualifiers/294 exact fresh replay scenarios. Shared low
risk cap suppresses second-half SELL admission. Stage6 research
`annual_m5_directional_sizing`48: seeds hybrid14/15 ×BUYcap2/2.5/5 ×BUYfixed/risk
×BUYTP2/3R ×SELLstop2/2.5ATR. Optional BUY risk/sizing override defaultsNone/inherits
shared; SELL fixed0.01/cap10 retained. Per-position lot/cost accounting unchanged,
floor and minimum rejection mandatory. Research-only ceiling20 still enforced
through shared allowed-cap values. Outcome pending; cost/holdout remain unverified.

Stage6 directional sizing48 completed0qualifiers/294 fresh exact scenarios. Stage7
`annual_m5_atr_reward`64 predeclared: eight M15profiles ×TTL2/4 ×BUYTP1.5/2R/off orBE1;
bothM5triggerstops, SELLTP3ATR/BE1R, fixed0.01/cap10/daily10/one loss/bounded24.
Optional sell_stop_mode None preserves legacy/shared; explicittrigger permits
shorter SELL risk with independent ATRreward. Actual costs/holdout remain pending,
no runtime promotion. Public SELL geometry RED->GREEN risk0.701USD vs3ATRtarget.

Equity/M5 checkpoint:8completecatalogs444parameter evaluations,0joint qualifiers;
2,712exact fresh full-result scenario repeats. Initial128M5runs preservedsuperseded,
excluded authoritativecount. Finalpublicsuite792/790pass2skip; Ruff5/scopedstrictmypy3
pass; legacy18whole-outcome matches with explicitly normalized defaultRules metadata.
[Report](docs/reviews/2026-10-03-equity-tuning.md) and
[hashed scenario/failure/funnel audit](docs/reviews/2026-10-03-equity-tuning-results.json).
Risk/entry framework implemented and reviewed; requested superiorstrategygoal UNMET,
commission/swapvalidation COST_INCONCLUSIVE, independentholdout sealedunaccessed,
Demo contract unchanged. Every finite campaign/repeat process completed.

### 6.29 Owner-authorized relaxed gates & Reward156 qualification (2026-10-04)

Owner explicitly approved targeted relaxation of research qualification gates:
- Drawdown ceiling relaxed from $\le 30.0\%$ to $\le 35.0\%$ absolute across all 6 scenarios.
- Half-window trade minimum relaxed from $\ge 20$ to $\ge 10$ trades.
- Invariants retained: net profit, win rate, and realized RR strictly above baseline in all 6 scenarios (RR $> 1.0$); full trades $\ge 60$; actual BUY+SELL fills; fixed 0.01 lot, 10% risk cap, 20% daily loss limit; single position only, no basket recovery.

Audit of ~4,000+ evaluated parameter contracts (`docs/reviews/artifacts/rescreen_relaxed_gates.py`) identified **10 qualified candidates**. Primary winner selected: **Reward156** (`RESEARCH-HYBRID-RSI7BUY-D48SELL-T156`):
- **BUY:** Rolling RSI(7) cross above 35 with positive delta, above EMA50, EMA50 rising over 4 bars.
- **SELL:** Prior 48-bar low breakout (`close < rolling_min(low, 48).shift(1)`). SELL priority on conflict.
- **Exit Geometry:** SL 2.5 ATR, TP 1.35x initial rounded stop distance, protection off.
- **Risk Circuits:** Fixed 0.01 lot, 10% equity risk cap, 20% daily limit, BUY pause at $\ge 5\%$ equity drawdown.
- **Performance:** Full base net +$883.77 (vs Trial30 +$465.32, +90%), full base DD 22.50% (vs Baseline 26.01%), full stress net +$742.03 (vs Baseline +$361.40, +105%), second-half stress net +$335.64 (vs Baseline +$12.17), 152 trades (23 BUY / 129 SELL).
- **Seam Implementation:** `scripts/strategy.py:reward156_bars` and `reward156_levels(entry, direction, atr)` verified with 100% signal parity against research frame (`tests/test_reward156_strategy.py`).
- **1-Year Annual Archive Replay (2025-10 to 2026-10):**
  - Second-half (Apr–Oct 2026): Net +$981.95 (Base) / +$933.21 (Stress), DD 22.50% / 22.97%, WR 56.41%, RR 1.2310, 156 trades (21 BUY / 135 SELL).
  - First-half (Oct 2025–Apr 2026): Net -$89.96 / DD 68.74%, consistent with baseline Trial30 (-$90.71 / DD 47.78% / 0% WR). 10% risk cap halted subsequent trades, preserving remaining capital.
  - Session37 alternative (avoid rollover > 21:00 UTC) yielded second-half net +$1,047.49 with DD 26.75% and zero overnight BUY swap exposure.
- **Demo runner retired (2026-10-04):** Reward156DemoRunner was never executable: nonexistent Journal APIs blocked sends, missing positions were incorrectly treated as CLOSED without a deal ledger. Removed runner and misleading tests; frozen `config/reward156-demo.json` remains research input. See `docs/reviews/2026-10-04-demo-replacement-scrutinize.md`.
- **Status:** Historical research results above retain their original scope. Demo readiness was unproven; real-money remains PROHIBITED. Candidate replacement requires its own broker parity, shadow and cutover gates.



### 6.30 Reward156 paired config tuning (2026-10-04)

Owner requests independent Reward156 versus current trial30 research replays on identical environments, followed by three frozen Reward156 config candidates. Protocol: `.cursor/plans/long-term_macro_gate_99f085f3.plan.md`; catalog: `config/reward156-tuning.json`; CLI: `python -m scripts.research.reward156_tuning --repeat`. Five contracts: unchanged trial30 D48SELL/TP3ATR/BE1R; original Reward156 RSI7cross35/EMA50BUY+D48SELL/rounded-stopTP1.35/BUYpause5%; no_pause; no_pause+closedH4EMA100; no_pause+closedH4EMA200. Shared fixed0.01/SL2.5ATR/10% cost-inclusive cap/daily20%/single-position; no recovery. Demo files/runners unchanged.

Dataset A discovery Sep2024-Jun2025 (10months, two reset5month halves), Dataset B Oct2025-Sep2026 (12months, two reset6month halves). Each dataset's full account continuous from USD200; halves reset account state only, indicator prefix remains causal. Same bars/ticks/specs/date/cost inputs for independent strategies. Base actualBidAsk/zero modeled slippage; stress spread+0.20USD/oz/slippage0.10USD/oz adverse market fills; commission0 assumed. Both no-swap and current-spec swap views independently replayed. Optional replay swap updates quoted-tick equity/DD, settlement, subsequent pause/cap/day-state; attribution net-before-swap does not represent separate no-swap equity path. Legacy default API/output preserved.

Swap research assumption: points mode, long-567.4/short0, point0.001/contract100 at0.01lot; UTCmidnight labelled preceding business day, Wednesday triple posts Thursday00UTC, Friday single posts Saturday00UTC, no additional weekend debits. Entry exactly at posting excludes prior-day debit. Quoted-tick accrual, no synthetic quotes; historical broker rates/rollover/DST/entitlement unverified, COST_INCONCLUSIVE. H4 requires16completeM15; EMAadjustFalse/min_periods100or200 seeded first eligibleH4, published only atH4close<=M15decision. Equality/missing/latestincompleteH4 blocks. No150barEMA200 live substitution or runtime parity claim.

Improvement requires positive swap net above original on both continuous datasets/base+stress, DD<=35/risk<=10/no observed final30day risk-only blockage. Qualification additionally retains trial30 comparison net/WR/RR>baseline, RR>1, DD<=35, full>=60/halves>=10, actualBUY+SELL in all12swap scenarios. Rank eligible candidates worstcontinuousDD ascending, then minimumcontinuousnet descending, then catalog order. Every120matrix cells requires full-result fresh repeat; hashes include source/config/input/runtime/spec. Jul-Sep2025 remains sealed unless one qualified candidate is locked; no retuning after opening. Research success never authorizes Demo cutover or real money.

Completed120cells with120complete-result fresh matches; baseline48cells written before candidate72cells. No candidate qualifies under frozen gates. Continuous swap-sensitivity H4EMA100 nets A base/stress+223.35/+139.10 and Bbase/stress+383.22/+362.78, but DD39.22/40.98/64.96/54.73% exceeds35%. EMA200 also failsDD and Bbase net-73.37. No_pause fails net/DD gates. These are in-sample model results, not broker-verified profit. Full matrix/provenance/verdict in `docs/reviews/reward156-tuning-2026-10-04/summary.md` and `COMPLETE.json`. Jul-Sep2025 remains unopened; no Demo modification or catalog expansion.

### 6.31 Reward156 profit/survival v2 research (2026-10-04)

Owner-approved follow-on protocol `profit_survival_v2` changes selection policy and opens entry/exit/filter configuration tuning. V1 results and qualification verdict remain immutable. Config `config/reward156-profit-survival.json`; CLI `python -m scripts.research.reward156_campaign`. Same A/B archived discovery windows, independent USD200 accounts, fixed0.01, single position, risk ceiling10%, actual Bid/Ask and base/stress costs as6.30. Strategy circuits may differ explicitly; trial30 and original Reward156 controls retain their own frozen daily20%/pause/protection logic. No Demo runner/config change, recovery or risk/lot escalation.

All8 continuous A/B/base/stress/no-swap/swap cells require net>=USD50 (+25%) and strictly greater than BOTH controls, DD<=45%, >=60trades, actualBUY+SELL, risk<=10%, positive equity/noBANKRUPT/no observed terminal risk-only blockage. All16 reset-half cells require net>=-USD20, DD<=45%, >=10trades and same risk/survival gates; no baseline-profit or direction requirement on halves. WR/RR report-only, undefined values preserved. EMA100 is benchmark. Qualification means modeled research scenarios only; historical swaps/commission/live fills remain unverified.

Registered seeds: H4EMA100/200 retain frozen Reward156 RSI7 zero-loss handling; archived circuit22/fine6/unpaused28 retain `campaign_signals` oscillator formula (zero-loss RSI100) and original directional horizons/exits/circuits. BUY EMA50 fixed. Configurable RSI7/14 threshold25/30/35, SELL Donchian24/48/96 with EMA0/50/200, H4EMA0/100/200; BUY SL1/1.5/2/2.5ATR and TP1.35/1.5/2R, SELL SL1.5/2/2.5ATR and TP3ATR/1.35/2R; per-side off/BE1R. Daily10/20%, max daily losses0/1/2, cooldown0/2/4M15bars, all/avoid-rollover21-24UTC, static/drawdown_steps cap with10% maximum. Cooldown accepts2 in offline Rules; legacy0/1/4 unchanged. BE preserves existing price/commission/slippage formula; swap may leave realized BE exit negative.

Finite search: screen5seeds, stop expansion if a seed qualifies final validation. Else top2seeds by numberpassing8continuouscells, worstnet descending, worstDD ascending, stableconfigID. <=27one-factor variants each; combine best signal/exit/circuit factor in3pairs+1triple each; dedup before execution; <=62newconfigs. Up to6finalists passing continuous screen receive24maincells and8additionalcontinuous swap0.5x/1.5x sensitivity cells, all fresh complete-result matches. Controls repeated fresh. Rank fully passing highest worstcontinuousnet, lowest worstDD, configID. Config/source/runtime/plan/input hashes guard resume and immutable catalogs.

Lock one winner before opening historical Jul-Sep2025 holdout; winner plus two controls share4maincostviews, independent USD200 and causal discovery indicator prefix. Holdout requires positive net above bothcontrols, DD<=45%, >=10trades, risk/survival gates. Failure stops without retuning. No qualifier means holdout stays sealed and profit objective unmet. Research qualification does not authorize Demo cutover or real-money execution.

Completed v2:5 seeds,52 deduplicated one-factor configs and8 combinations =65 candidates,584 replay cells. Controls cover64 full/half/main/additional-swap cells with64 fresh complete-result matches;48 main control results also exactly match v1. No candidate passes all8 continuous screening cells, so candidate reset-half/additional-swap validation and historical holdout are cancelled, not passed. No selection lock or holdout input created.

Highest-ranked measured candidate `variant_1af968e9ac6a26ea` is archived circuit22 plus closedH4EMA200: RSI14cross25/EMA50BUY, D96/EMA50SELL; BUY SL1.5ATR/TP2R/protectionoff; SELL SL2.5ATR/TP3ATR/BE1R; daily10%/one losing exit perUTCday, fixed0.01/static10% cap, no BUY pause. It earns positive net above BOTH controls in all8 continuous cells. A base/no-swap +37.63, base/swap +37.06, stress/no-swap +30.31, stress/swap +29.74;32 trades,DD24.64–25.68%. B corresponding nets +188.07/+186.93/+293.67/+292.53;72 trades,DD28.29–35.60%. Worst net +29.74, worstDD35.60%;4/8 v2 cells pass. All four A cells fail net>=50 and trades>=60. This is measured discovery improvement, not full v2 qualification or a guaranteed profitable replacement.

Independent artifact audit reconciles51,010 ledger trades, lot/cost-inclusive risk/single-position invariants, source/dataset/checkpoint hashes, complete metrics/gates, adaptive catalog and winner selection. Full suite831tests21.448seconds OK(skipped2); changed-Python Ruff and syntax compilation pass, no configured typechecker. First104-cell attempt failed native JSON serialization of NumPybool; preserved separately and corrected source reran the entire catalog without changing policy. Canonical evidence: `docs/reviews/reward156-profit-survival-2026-10-04/summary.md`, `validation.json`, `completion-audit.md`, `COMPLETE.json`. Profit qualification remains unmet; COST_INCONCLUSIVE and unchanged trial30 Demo remain.

### 6.32 Owner-requested four-strategy continuous whole-history comparison (2026-10-04)

Owner requested only trial30, original Reward156, circuit22+H4EMA200 (`variant_1af968e9ac6a26ea`) and fine6+H4EMA200 (`variant_a970d2864f1fade4`), from first available paired archive through present. New retrospective comparison; no tuning or previous qualification relabeling. Requested2024-09-01 through frozen2026-10-04T11:19:48.476278UTC; actual quotes2024-09-01T22:05:06.129UTC through2026-10-02T20:57:59.885UTC. Same public Exness feed,167,366,065 ticks/48,367 completedM15bars;25fullmonths plus partialOct2026. Each strategy/view startsUSD200 once, fixed0.01/cost-inclusive cap10%/single position; no account/peak/risk/day/indicator reset at dataset or year seams. Daily circuits/exits stay strategy-specific as6.31. Four base/stress/no-swap/current-spec-swap views; commission0 and historical-swap/rollover assumptions remain COST_INCONCLUSIVE.

**Jul–Sep2025 now opened under explicit whole-history request.** It cannot be reused as untouched independent holdout for these strategies. Prior6.30/6.31 unopened statuses describe their historical campaigns; no old artifacts or verdicts changed. Whole-history performance includes previously excluded months, continuous equity/admission path and full causal EMA prefix, so it differs from independently reset A/B results.

Swap-inclusive base/stress netUSD: trial30 -155.60/-144.95 (final44.40/55.05), originalReward156 -143.34/-154.72 (final56.66/45.28), circuit22+H4EMA200 +291.55/+278.71 (final491.55/478.71), fine6+H4EMA200 +333.97/+272.44 (final533.97/472.44). WorstDD acrossall4views78.46/79.80/39.28/40.95%, respectively. Candidate worstnet across4views+246.81/+225.87; both positive abovecontrols throughout modeled environments. Circuit22 more favorable worstnet/DD; fine6 higher base profit. Neither candidate retains DD<=35% on this full path; fine6's old29.39% DD belongs to separateA/B accounts. Controls do not bankrupt but end with no new admission for~404–410days; originalReward156 mixed BUYpause/risk reasons prevent risk-only terminal flag from implying normal activity.

Completed16cells/16fresh whole-result matches (32replaycalls). Independent verifier recomputed row metrics/DD from equity checkpoints, reconciled1,494 scenario ledger trades, cost-risk/equity/fixedlot/non-overlap and input/source hashes. Existing regression65tests0.528seconds OK; artifact Ruff/syntax pass. Report `docs/reviews/2026-10-04-four-strategy-continuous-backtest.md`; full local evidence `data/research_output_four_strategy_full_history_2026_10_04/`. No production strategy/config/journal/process/order change. Favorable research returns do not fix Reward156 runner's Journal/reconciliation/candidate-parity gaps identified in `docs/reviews/2026-10-04-demo-replacement-scrutinize.md`; Demo replacement readiness remains unresolved.

### 6.33 Frozen circuit22 + closed H4 EMA200 Demo replacement (2026-10-04)

Owner selected `variant_1af968e9ac6a26ea` for replacement of trial30 on the same Exness Demo account, accepting modeled worst DD 39.28%. Snapshot `RESEARCH-C22-H4EMA200-20261004`; fixed 0.01 lot, static cost-inclusive equity cap 10%, single position, no recovery baskets, real money **PROHIBITED**. Continuous historical modeled swap-inclusive base/stress net +$291.55/+$278.71 remains retrospective research evidence, not profitability qualification or broker cost parity. Source: `docs/reviews/2026-10-04-four-strategy-continuous-backtest.md`.

Frozen detector is exactly `reward156_search.prepare_candidate` with archived circuit22 recipe and `macro_span=200`, config ID `1af968e9ac6a26ea`. BUY: campaign RSI14 crosses >=25 from below, positive close delta, close>EMA50, EMA50>EMA50[-4]; zero-loss RSI=100. SELL: close<prior 96-bar low, close<EMA50, EMA50<EMA50[-4]; SELL wins conflicts. Both require directional agreement with closed H4 EMA200; unavailable macro blocks. UTC Bid M15 uses all 15 M1 minutes, never forming bars. Cache bootstraps 100000 broker M1 bars once, requires >=201 complete H4 and fetch/assembly <60 seconds, then appends completed M15 from 5000-M1 tail. Changed, added or missing overlap blocks current cycle as `bar_cache_divergence`; next admission cycle rebuilds. No archive seeding or disk bootstrap fallback selected.

BUY SL=1.5 ATR, TP=2 times **rounded** entry-stop distance, protection off. SELL SL=2.5 ATR, TP=3 ATR, BE only at closed-bar first quote net >=1R. Canonical `breakout_entry.prepare_entry` uses modeled adverse entry=Ask+slippage (BUY) or Bid-slippage (SELL); actual market request price uses current Ask/Bid. Stop/target grid rounds toward risk (BUY floor, SELL ceiling). Risk=(abs(modeled entry-stop)+exit slippage)*contract_size*0.01+round-trip commission_per_lot*0.01. Broker profit calculation independently checks risk before send and after confirmed fill using freshly verified entry equity; never clamps volume. Flat research balance admission maps to live equity admission. Broker actual fills, quote/entry window, margin, stop/freeze levels and cost evidence can reject a research signal.

Daily UTC equity loss limit 10%, max **one losing completed position per exit UTC day**, cooldown0, no BUY pause, all sessions. Restart-safe loss count routes C22-owned opening deals (magic `22261004`, `C22_` comment) to position IDs, then sums complete ledger profit+commission+swap+fee. Flat volume and net<0 count a loss on last exit day; closing magic/comment need not match. Demo broker-confirmed FILLED/CLOSED/BE events and outbox reuse trial30 Journal unchanged. SENDING/UNKNOWN remain unresolved until complete broker evidence; unexpected fill risk/volume/stops/costs close only owned ticket and halt further admission.

Shared lifecycle has trial30 default hooks and candidate hooks; 27 existing trial30 lifecycle tests remain unchanged. Local account fingerprint writer guard is acquired before MT5 initialization and excludes simultaneous trial30/c22h4 writers with separate journals. CLI uses same canonical account-guard directory even for journal overrides. Candidate journal `data/c22h4-demo.sqlite3`; trial30 journal/config/targets retained for rollback. Config pins contract plus research/detector/bar-assembly SHA256; `source_drift` blocks admission while existing trades continue reconciliation/protection. Cost policy reused, owner attestation <=24 hours; stale policy blocks entries.

**Implementation readiness differs from operational readiness:** offline code/test review can proceed, but initial Wine broker probe failed `wine: cannot find the server port: 0x0000044c`. Broker depth/latency/maximum and archive parity remain unverified. No fallback selected, no shadow qualification, no Demo cutover, no orders sent by this implementation session. Required next gates: read-only history/parity, >=96 completed-M15 shadow bars spanning UTC midnight with exact exported-cache replay, fresh owner cost attestation, flat trial30/empty outbox/stopped watcher/no trial30 trade that UTC day, then owner cutover approval. First broker close must record closing magic/comment. Ops: `docs/ops/c22h4-demo.md`; evidence/status: `docs/reviews/2026-10-04-c22h4-implementation.md`.
