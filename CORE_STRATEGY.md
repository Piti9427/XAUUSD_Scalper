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
