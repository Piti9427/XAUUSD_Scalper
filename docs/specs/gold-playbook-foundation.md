# Gold Playbook Foundation — Exness Demo, CHoCH และ Fibonacci Research

## Problem Statement

ผู้ใช้ต้องการระบบเทรดทอง XAUUSD ที่มีพื้นฐานเป็นระบบ สามารถวัดกำไรสุทธิและพิสูจน์อัตราชนะมากกว่า 50% ก่อนพิจารณาเงินจริง โดยเริ่มจาก Exness Standard Demo ทุน USD 500 ใช้ Mac สำหรับพัฒนา และ Oracle ARM64 VM สำหรับระบบที่ต้องทำงานต่อเมื่อปิด Mac

ระบบปัจจุบันมีองค์ประกอบ Sweep, fractal, MSS, FVG, risk sizing, replay, execution และ notification แต่ผล review พบว่าการจำลองกับการส่งคำสั่งยังเดินคนละเหตุการณ์ได้ เช่น fill-and-stop ในแท่งเดียวไม่ถูกบันทึก, การตีความ SL/TP ไม่ตรงกัน, การข้าม fill เพราะ spread สูง และการล้าง pending ก่อน broker ยืนยันยกเลิก นอกจากนี้ MSS ปัจจุบันเป็นการปิดทะลุ fractal ล่าสุด โดยไม่มีสถานะโครงสร้าง M5 ที่แยก CHoCH ออกจาก BOS

บัญชีนี้มีการเทรดมือหรือระบบอื่นร่วมด้วย จึงต้องแยกผลกลยุทธ์ของ bot ออกจาก risk controls ของทั้งบัญชี และไม่จัดการคำสั่งที่ bot ไม่ได้เป็นเจ้าของ การมีชื่อเทคนิคหลายชนิดหรือ unit tests ผ่านยังไม่ใช่หลักฐานว่ากลยุทธ์ทำกำไร

## Solution

สร้าง BaselinePlay เพียงชุดเดียวที่อธิบายและตรวจย้อนหลังได้: H1 directional bias → liquidity sweep → CHoCH ของโครงสร้าง M5 → displacement qualification → FVG confirmation → limit ที่ Consequent Encroachment → structural SL และ nearest eligible opposing liquidity TP ภายใต้ risk budget ของบัญชีจริง

ใช้ logic และวงจรเหตุการณ์ร่วมกันระหว่าง replay และ Demo ให้ broker-confirmed events เป็นหลักฐานของสถานะคำสั่งและการแจ้งเตือน บันทึกเหตุผลตั้งแต่พบ setup จนถึงถูกปฏิเสธ, หมดอายุ, fill หรือปิดสถานะ เพื่อให้เห็นว่า setup ใดเปิดได้จริงด้วยทุน USD 500

Fibonacci เป็นข้อมูลประกอบการวิจัยใน baseline นี้: บันทึก retracement และการอยู่ใน OTE โดยยังไม่กรองหรือย้ายจุดเข้า การเพิ่มตัวกรองภายหลังต้องเป็นการทดลองที่มี version และประเมินกับข้อมูลที่ไม่ได้ใช้เลือกกฎ

ผลส่งมอบแยกความพร้อมของ software/runtime ออกจากหลักฐานความได้เปรียบของกลยุทธ์ มีผลประเมิน PASS, FAIL, INCONCLUSIVE และ DATA_INSUFFICIENT ที่ไม่ปะปนกัน Demo 12 สัปดาห์เป็นรอบประเมินที่ตกลงกัน ไม่ใช่คำรับรองว่าจะมีข้อมูลมากพอหรือทำกำไร

## User Stories

1. As a Demo account owner, I want the system to verify my broker, account type, currency, and symbol, so that results apply to the account I actually use.
2. As a Demo account owner, I want the system to use my actual balance and equity, so that a hardcoded research balance cannot determine order size.
3. As a Demo account owner, I want each new trade to respect the agreed 0.5% risk budget, so that minimum-volume rules cannot silently increase my risk.
4. As a Demo account owner, I want unaffordable setups to be skipped with a reason, so that the system does not narrow structural stops or round volume upward to force a trade.
5. As a shared-account owner, I want account-wide trading activity to affect my risk limits, so that manual losses are not invisible to the bot.
6. As a shared-account owner, I want the bot to manage only its own orders and positions, so that my other trading remains under its original owner's control.
7. As a shared-account owner, I want manual activity and cash flows recorded separately from bot performance, so that I can explain changes in equity and trade selection.
8. As a Demo account owner, I want trading to stop after two losing trades or a 1% daily equity decline, so that the agreed daily circuit breaker is enforced.
9. As a Demo account owner, I want a 5% equity drawdown halt to survive restarts, so that restarting software cannot erase a risk breach.
10. As a Demo account owner, I want a drawdown halt to request cancellation and closure of bot-owned exposure, so that known exposure is actively handled without touching other trades.
11. As a strategy owner, I want H1 bias calculated from closed data, so that unfinished candles cannot change historical entry decisions.
12. As a strategy owner, I want M5 structure classified separately from H1 bias, so that an EMA direction is not mistaken for a CHoCH.
13. As a strategy owner, I want BOS and CHoCH distinguished using explicit structural swing rules, so that continuation and reversal setups are not mixed under one label.
14. As a strategy owner, I want a confirmed M5 CHoCH required before entry, so that the baseline follows the reversal logic I selected.
15. As a strategy owner, I want minor internal swing breaks distinguished from protected-swing breaks, so that small fluctuations do not automatically qualify as structural reversals.
16. As a strategy owner, I want unknown or ranging structure represented explicitly, so that missing structure is not converted into a confident directional signal.
17. As a strategy owner, I want swing confirmation times recorded, so that a pivot cannot be used before the required right-hand candles close.
18. As a strategy owner, I want sweep and breakout rules stated precisely, so that wick rejection and structural penetration produce reproducible outcomes.
19. As a strategy owner, I want displacement qualification measurable and versioned, so that a candle-body percentage is not silently treated as proof of unusual momentum.
20. As a strategy owner, I want the agreed Sweep-to-MSS and MSS-to-FVG windows enforced, so that stale price patterns cannot create fresh entries.
21. As a strategy owner, I want the FVG's third candle closed before any order, so that replay cannot fill an order before its setup was knowable.
22. As a strategy owner, I want entry at the FVG midpoint, so that the system uses the selected entry model consistently.
23. As a strategy owner, I want stop loss anchored to True Swing Extremum, so that account sizing does not redefine where the setup is invalid.
24. As a strategy owner, I want TP at the nearest eligible opposing liquidity pool, so that the system does not select a farther target to manufacture a favorable R ratio.
25. As a strategy owner, I want already-consumed pools excluded at target selection, so that a previously touched level is not reported as untouched liquidity.
26. As a strategy owner, I want setup identity, expiry, and invalidation preserved, so that retries and restarts cannot revive the same expired opportunity.
27. As a strategy researcher, I want Fibonacci anchors and retracement recorded at decision time, so that later swing information cannot improve historical confluence.
28. As a strategy researcher, I want OTE membership logged without filtering baseline trades, so that I can study Fibonacci before changing the strategy.
29. As a strategy researcher, I want Fibonacci retracement separated from the FVG midpoint, so that two different price ranges are not confused.
30. As a Demo account owner, I want new and pending exposure blocked around scheduled high-impact USD news, so that the agreed blackout applies to order admission.
31. As a Demo account owner, I want existing positions to retain their SL and TP through news, so that the system follows my decision against a special pre-news exit or breakeven rule.
32. As an operator, I want unknown or stale market, account, and news data to block new risk, so that missing information is not interpreted as permission to trade.
33. As an operator, I want order acceptance, fills, cancellation requests, and completed cancellations distinguished, so that the local state matches broker reality.
34. As an operator, I want fills during cancellation, partial fills, rejects, and timeouts reconciled, so that difficult broker outcomes do not disappear from the ledger.
35. As an operator, I want durable intent identity and restart reconciliation, so that uncertain submissions are not blindly sent twice.
36. As a notification recipient, I want order messages to describe broker-approved or executed states accurately, so that an unexecuted signal is never presented as an open trade.
37. As a strategy researcher, I want replay to use ordered bid/ask quotes and realistic order timing, so that entry and exit prices reflect executable sides of the market.
38. As a strategy researcher, I want every filled position recorded including immediate losses and time exits, so that accounting omissions cannot inflate profitability.
39. As a strategy researcher, I want research results separated from USD 500 executable results, so that theoretical opportunities are not presented as attainable account performance.
40. As a strategy researcher, I want bot-only replay distinguished from shared-account replay, so that absent manual events are not hidden behind a claim of live parity.
41. As a strategy researcher, I want net trading profit and net operating profit reported separately, so that fixed running costs do not disappear from the profitability claim.
42. As a strategy researcher, I want a frozen statistical and cost-stress protocol, so that PASS criteria cannot be chosen after viewing outcomes.
43. As a strategy researcher, I want low trade counts reported as insufficient evidence, so that the system does not invent trades or loosen rules to meet a quota.
44. As a strategy researcher, I want a 12-week forward Demo assessment, so that operational and strategy evidence is collected prospectively.
45. As an operator, I want the system to remain available when my Mac is off, so that the runtime does not depend on my development computer.
46. As an operator, I want a bounded Oracle ARM64 compatibility experiment, so that unsupported emulation does not consume an unlimited engineering effort.
47. As an implementer, I want one high-level behavioral test boundary shared by replay and Demo orchestration, so that tests check the complete trading lifecycle instead of disconnected helpers.
48. As a project owner, I want unresolved material decisions identified explicitly, so that an agent does not silently convert a proposal into an approved trading rule.
49. As a project owner, I want a separate approval boundary for real-money deployment, so that a Demo spec or readiness label cannot authorize live capital.

## Implementation Decisions

### 1. ข้อตกลงที่ผู้ใช้ยืนยัน

- Broker/account: Exness Standard Demo; instrument ที่ผู้ใช้ระบุคือ XAUUSD; starting capital USD 500 ต้องตรวจชื่อ symbol จริง, currency, account identity และ broker specification ก่อนเปิด Demo orders
- เป้าหมายคือ expectancy สุทธิเป็นบวกและ win probability มากกว่า 50% โดยใช้ lower confidence bounds ที่ระดับ 95%; ยังไม่มีหลักฐานว่ากลยุทธ์นี้บรรลุเป้าหมาย
- Risk ต่อ trade 0.5%; ห้าม minimum-lot override ให้เกิน budget ถ้าเปิดขั้นต่ำแล้วเสี่ยงเกินให้ข้าม ไม่เพิ่มทุนสมมติ ไม่บีบ structural SL เพื่อให้เปิดได้
- บัญชีมี manual/other trading ร่วมด้วย: daily risk และ drawdown มองทั้งบัญชี; strategy performance มองเฉพาะ bot; bot จัดการได้เฉพาะ exposure ของตน
- Daily stop: สอง trades ที่ขาดทุนสุทธิ หรือ equity ลดลง 1% จากต้นวัน UTC แล้วแต่ว่าเกิดก่อน
- Equity drawdown 5% จาก high-water mark: halt แบบคงอยู่ข้าม restart, request cancel pending และ request close positions ของ bot แล้วรอ review ไม่ reset อัตโนมัติ
- Require M5 CHoCH ก่อนเข้า ไม่ใช้ BOS หรือการทะลุ fractal ใดก็ได้แทน CHoCH; H1 EMA200 bias ยังเป็นตัวกรองฝั่งแยกต่างหาก
- Fibonacci บันทึกข้อมูลก่อน ยังไม่ใช้เป็น entry filter; OTE 62–79% เป็น research tag ของจุดเข้า ไม่ใช่การเปลี่ยน entry เป็นราคา Fibonacci
- TP เป็น nearest untouched opposing pool ณ การเลือกเป้าหมาย; ถ้า nearest eligible target ให้ planned R ต่ำกว่า 1.5 ให้ข้าม ไม่ขยายไปพูลไกลเพื่อให้ผ่าน R
- ไม่มี partial profit-taking หรือ breakeven ใน baseline; broker partial fills เป็นเหตุการณ์ execution ที่ต้องรองรับและไม่ใช่กลยุทธ์แบ่งปิดกำไร
- News blackout: USD HIGH ก่อนและหลังเวลา release 30 นาที ห้าม new/pending exposure; positions ที่เปิดแล้วถือด้วย SL/TP เดิม ไม่มี forced pre-news exit หรือ pre-news BE เป็นกรณีพิเศษ กฎ risk halt และ time exit ยังมีผล
- Sweep → MSS ภายใน 8 แท่ง; MSS → FVG middle candle ไม่เกิน 4 แท่ง และต้องรอ right-hand candle ปิดก่อนส่ง order
- ใช้ M5/H1 พร้อม bid/ask ticks เพื่อ replay; ไม่มี M15 proxy สำหรับหลักฐานสุดท้าย
- ไม่กำหนด trade quota; ความถี่ 2–5 trades ต่อเดือนยอมรับได้ แต่ผลอาจเป็น INCONCLUSIVE
- Forward Demo รอบแรก 12 สัปดาห์; ใช้ Demo ก่อน และการใช้เงินจริงต้องมีการอนุมัติแยก
- Runtime ต้องทำงานต่อเมื่อ Mac ปิด ใช้ Oracle ARM64 VM ที่มีอยู่ก่อน; timebox Box64 → Wine64 → MT5 และ Windows Python หนึ่งวันวิศวกรรมสำหรับ compatibility ตามด้วย soak/restart/reconnect 48 ชั่วโมง ถ้าไม่ผ่านให้รายงานผลและกลับมาทบทวน platform ไม่เพิ่มบริการเสียเงินเอง

### 2. Baseline ทางเทคนิคที่สืบทอด และการแก้ความหมายของ domain

- Existing baseline: closed H1 Close เทียบ EMA200; เท่ากันไม่มี directional bias; M5 เป็น execution timeframe
- ใช้ fixed UTC admission windows London 07:00–10:30 และ New York 12:30–16:30 ไม่ปรับ DST หรือเปลี่ยนเป็นเวลาท้องถิ่นอย่างเงียบ ๆ
- Candidate baseline parameters จากเอกสารเดิม: body ratio 45%, FVG minimum USD 0.30 ของราคาทอง, sweep pierce maximum USD 8, sweep lookback 25 bars, structural buffer USD 0.30, SL cap USD 25, pending TTL 4 M5 bars และ time-exit request ที่ 20:55 UTC ค่าเหล่านี้เป็น configuration ของสมมติฐาน ไม่ใช่ค่าที่พิสูจน์แล้วว่าเหมาะที่สุด
- Spread guard USD 0.35 และ cooldown หลัง loss 30 นาทีเป็น baseline proposals ที่เคยเสนอ ต้องระบุใน frozen rule set พร้อมหน่วยและ trigger ที่แน่นอนก่อนวัดผล ห้ามแปลง broker points ด้วยตัวคูณสมมติ
- Body ratio เป็นสัดส่วนรูปร่างแท่ง ไม่ใช่มาตรวัดขนาด impulse เทียบ volatility โดยตัวมันเอง การเพิ่ม ATR/relative-range filter เป็น strategy change ไม่รวมอัตโนมัติ
- Bullish FVG: low ของแท่งขวาสูงกว่า high ของแท่งซ้าย; bearish FVG กลับด้าน ต้องแก้นิยาม bullish ที่กลับด้านใน glossary เดิม ไม่แก้ detector ให้ตาม typo
- Consequent Encroachment คือ midpoint ของ FVG; แยกจาก midpoint/Fibonacci ของ swing
- Liquidity Pool ในระบบเป็นระดับราคาอ้างอิงจาก Asian range, PDH/PDL และ London range ไม่ใช่หลักฐานว่าเห็น stop orders ของตลาดจริง
- Asian range ใช้ 00:00–07:00 UTC; London range ใช้ 07:00–12:00 UTC และใช้ได้หลังช่วงนั้นครบแล้วเท่านั้น; PDH/PDL ต้องมาจาก previous trading day ที่มี coverage เพียงพอ ไม่มี fallback ปลอมเป็น Asian levels เมื่อข้อมูลหาย
- แต่ละ pool ต้องระบุ identity, source period, available time และ consumption history; ตัดสิน eligibility ด้วยข้อมูลที่รู้ ณ เวลานั้น เป้าหมาย BUY อยู่เหนือ entry และ SELL อยู่ต่ำกว่า entry
- Normalize ราคาด้วย broker tick size และ volume ด้วย broker volume step แล้วประเมิน R, risk และ margin ใหม่ ใช้ True Swing Extremum ระหว่าง Sweep ถึง MSS พร้อม structural buffer เป็น SL reference
- แยกนิยาม CHoCH, BOS, protected swing, internal swing, MSS และ Fibonacci anchors ใน glossary; นิยามที่ยังไม่ตกลงอยู่ใน Further Notes ห้ามแอบใช้ latest-fractal implementation เป็นคำตอบ
- เก็บประวัติ ADR เดิมและระบุการ supersede ของ MSS, TP/scale-out, news, minimum-lot override และ notification coupling สำหรับ baseline นี้ แยก glossary ออกจาก implementation decisions โดยรักษาประวัติข้อตกลง

### 3. ขอบเขตโมดูลและ interfaces

- ใช้ seams เดิมของ pure detection, orchestration, broker adapter และ notification ก่อนเพิ่ม abstraction ใหม่
- Pure detection รับ market snapshot ที่ทราบ ณ decision time และ versioned rules แล้วคืน SetupDecision พร้อม eligibility/rejection reasons ไม่มีการเรียก broker, คำนวณ lot หรือส่งข้อความภายใน
- Structure state ต้องแยก timeframe, directional state, swing identities, confirmation time และ event classification เพื่อให้ test สามารถแยก BOS, CHoCH และ UNKNOWN ได้
- Setup identity ต้องผูกกับเหตุการณ์และ version ของกฎ ไม่สร้างใหม่เพียงเพราะประเมินซ้ำ; เก็บ sweep time, structural-break time, FVG confirmation time และ expiry แยกจากเวลารัน detector
- Orchestration เป็นเจ้าของวงจร setup/order/risk โดยรับ ordered market, clock, account และ broker events; replay และ Demo ใช้วงจรนี้ร่วมกัน
- Replay รับ dataset manifest, rules, risk policy, broker specification และ external account events เมื่ออ้าง shared-account parity แล้วคืนรายงานพร้อม lifecycle ledger และเหตุผลที่ถูกข้าม
- Adapter result แยก ACCEPTED, REJECTED และ UNKNOWN จากสถานะ lifecycle ของ order; การตอบรับ request ไม่เท่ากับ fill
- Durable ledger บันทึก intent ก่อนส่ง, broker order/deal identifiers, ownership, event time, observation time และ reconciliation result โดยมี idempotency สำหรับ event และ intent
- Notification อ่านสถานะที่ยืนยันแล้ว: accepted pending order ต้องสื่อว่า pending; filled/closed ต้องอิง broker evidence ไม่อิงแท่งเทียนหรือ intent อย่างเดียว
- Fibonacci feature records ต้องมี anchor identity/time, entry retracement และ OTE membership; record ที่คำนวณไม่ได้ต้องเป็น unavailable พร้อมเหตุผล ไม่แทนด้วยค่า 0 หรือบังคับข้าม trade เพราะเป็น feature ที่ยังไม่กรอง

### 4. Broker lifecycle และ account risk

- วงจรต้องแยก submission pending, accepted, partial fill, filled, cancel requested, canceled, expired, rejected และ unresolved state ใช้ broker evidence reconcile ก่อน retry
- Spread, TTL, news หรือ risk policy สามารถ request cancel ได้ แต่ห้ามถือว่ายกเลิกสำเร็จก่อน broker ยืนยัน หาก fill เกิดก่อน cancellation สำเร็จต้องรับรู้และจัดการ position นั้น
- ห้ามใช้ spread guard ลบ fill ที่เกิดขึ้นจริงจาก ledger; replay ต้องจำลองลำดับ quote, request, acceptance และ cancellation อย่างมีเวลา ไม่ใช้ข้อมูลปลายแท่ง veto เหตุการณ์ต้นแท่ง
- Broker partial fills ต้องแสดง filled volume และ remaining pending volume พร้อมกันได้ และ reconcile เมื่อ residual ถูกยกเลิกหรือหมดอายุ
- คำนวณ volume โดยปัดลงตาม broker step และรวมต้นทุนที่ระบุใน cost model ห้าม clamp ขึ้นจนเกิน risk percentage; หาก metadata, conversion หรือ margin check ไม่พร้อมให้ไม่รับ new risk
- Risk base ที่เสนอคือ min(balance, equity); สถานะของข้อเสนอนี้และการจัดการ cash flows ต้องล็อกตาม Further Notes ก่อน freeze ไม่ถือเป็นคำตอบที่ผู้ใช้ยืนยันแยกแล้ว
- Daily/equity risk state ต้องใช้ข้อมูลทั้งบัญชีพร้อม timestamps และ persist ข้าม process restart; incomplete/stale account history ห้ามทำให้ daily loss count หรือ high-water mark กลับเป็นศูนย์
- Ownership ต้องตรวจด้วย account identity, dedicated strategy identifier และ broker order/position linkage; ตรวจ hedging/netting mode ก่อนเปิดใช้งาน หากแยก ownership อย่างปลอดภัยไม่ได้ให้ Demo execution gate ไม่ผ่าน
- Manual trades ส่งผลต่อ account controls แต่ไม่รวมเป็น bot trade PnL; manual intervention ต่อ bot-owned position ต้องเปิดเผยในผล ไม่ลบ trade ที่เสียออกเพื่อทำให้สถิติดีขึ้น
- Risk budget และ halt trigger เป็นนโยบายการรับและลด exposure ไม่ใช่การรับประกันขาดทุนสูงสุดเมื่อเกิด gap, slippage, manual activity หรือ outage
- Time exit และ risk close เป็นคำขอปิดจนกว่า broker จะยืนยัน; ใช้ clock events ไม่รอให้มี M5 bar ใหม่เพื่อเริ่มจัดการความเสี่ยง
- เมื่อข้อมูลหรือ connectivity ไม่พร้อมให้หยุดรับ risk ใหม่และ reconcile exposure ที่รู้จัก ห้ามเปลี่ยน execution failure เป็น dry-run success โดยอัตโนมัติ

### 5. Data, replay และ economics

- All timestamps เป็น timezone-aware UTC; แยก bar-open, bar-close, decision, request, broker-event และ observed times
- ใช้เฉพาะ closed candles และ pivots ที่ยืนยันแล้ว ณ เหตุการณ์นั้น; การเปลี่ยนข้อมูลอนาคตต้องไม่เปลี่ยน prefix ของผลลัพธ์
- EMA warmup และ seed/history convention ต้องเหมือนกันใน replay กับ Demo; ข้อเสนอเดิมคือ H1 warmup 1,000 bars แต่ต้องตรวจ coverage และล็อก convention ก่อนวัดผล
- Historical dataset proposal คือ 2025-09-01 ถึงก่อน 2026-09-01: development 9 เดือน และ holdout 3 เดือน โดยต้องยืนยันว่า holdout ยังไม่ถูกใช้เลือกกฎ หากปนเปื้อนต้องเปลี่ยนเป็นข้อมูลที่ยังไม่เห็น
- บันทึก hashes/version ของ quotes, bars, news, rules, cost model และ code; ตรวจ sorting, duplicates, missing coverage และ symbol metadata
- Exness public tick archive ไม่อนุญาตเลือก trading server และอาจต่างจาก Demo feed ต้องระบุ provenance และกำหนดวิธีตรวจความสอดคล้องของ bars/ticks ไม่กล่าวอ้าง exact-feed parity โดยไม่มีหลักฐาน
- Historical news ต้องมี source และหลักฐานว่ากำหนดการ/ระดับ impact นั้นรู้ได้เมื่อใด; current-week feed ไม่ใช่ historical archive และ feed unavailable ไม่ใช่ไม่มีข่าว
- ใช้ bid/ask ให้ถูกด้านและรวม order availability/latency; ห้าม fill ก่อน right-hand FVG candle ปิดและ order สามารถอยู่ในตลาดได้จริง
- Tick ordering เป็นตัวตัดสินลำดับ SL/TP; OHLC-only conservative SL-first ใช้เป็น diagnostic fallback ที่ติดป้ายเท่านั้น ไม่ใช้แทน tick-based evidence สำหรับ PASS เมื่อ ordering ไม่ทราบ
- ทุก filled position ต้องมี ledger outcome แม้เข้าแล้วโดน SL ในแท่งเดียว; TIME_EXIT จัด win/loss/flat จาก net PnL ไม่จัดตามชื่อ exit reason
- ไม่มี fill ให้เป็น NO_FILL และไม่นับใน win-rate denominator; canceled/rejected/expired setups ยังอยู่ใน funnel และ operational report
- Aggregate broker deals ที่เป็น position lifecycle เดียวกันก่อนนับ trade; นิยาม net PnL รวม fees, swap และ execution costs ตามจริง/แบบจำลองโดยไม่หัก spread ซ้ำหากอยู่ใน bid/ask prices แล้ว
- R ใช้ initial risk denominator ที่ตรึงและอธิบายได้ พร้อมรายงาน dollar PnL จาก volume/contract จริง ไม่ใช้สมมติว่าใช้ risk budget เต็มทุกครั้ง
- แยก theoretical setup tape, executable USD 500 replay, shared-account replay และ actual Demo report; หากไม่มี external account events ห้ามอ้าง shared-account parity
- Report funnel: detected, structure-qualified, target-qualified, affordable, risk-admitted, submitted, broker-accepted, filled และ closed พร้อม skip/reject reasons
- ทำ affordability report ก่อนลงทุนกับระบบเต็มชุด: สเปกทั่วไป 100 oz/lot และ minimum 0.01 lot ทำให้งบ USD 2.50 รับระยะ Entry-to-SL ได้ไม่เกินประมาณ USD 2.50 ก่อนต้นทุนเพิ่มเติม ต้องยืนยัน runtime specification และวัดจำนวน setup ที่ผ่านจริง
- แยก net trading profit จาก net operating profit หลังค่า runtime/data/service ที่เกิดขึ้นจริง ห้ามรายงาน expectancy ต่อ trade เป็นหลักฐานว่าระบบหลังหักค่าใช้จ่ายดำเนินงานมีกำไรแล้ว

### 6. Evidence และ rollout gates

- Gate A — นิยาม/fixtures: ปิด material decisions ที่ระบุใน Further Notes, freeze examples และ rule version ก่อนใช้ผลมาปรับกลยุทธ์
- Gate B — data/causality/accounting: dataset provenance พร้อม, causal tests ผ่าน, immediate loss/SL-TP/TIME_EXIT accounting ถูกต้อง และ affordability report มีหลักฐาน
- Gate C — execution/runtime: broker lifecycle, ownership, risk persistence และ reconciliation ผ่านทั้ง deterministic tests และ Demo verification; Oracle compatibility/48-hour soak เป็นข้อกำหนด runtime แยกจาก profitability
- Gate D — prospective evidence: holdout และ forward Demo ประเมินแยกตาม protocol ที่ freeze ไว้; ไม่รวม simulated กับ actual trades เป็น sample เดียวเพื่อให้ผ่านเร็ว
- 12 สัปดาห์เป็น formal Demo assessment window; ไม่มี early PASS และไม่มีการขยาย/ทดสอบซ้ำจนได้ผลชนะโดยไม่ลงทะเบียน protocol รอบใหม่
- รายงาน win rate จาก net-winning closed bot trades หารด้วย closed bot trades ทั้งหมด รวม flat ใน denominator; แสดงจำนวน win/loss/flat, expectancy net R, dollar PnL, profit factor, equity drawdown, losing streak และ breakdown ตามเดือน/session
- ต้อง freeze ความหมายของ lower confidence bound 95%, dependence handling และ cost-stress scenarios ก่อน evaluation; profit factor มากกว่า 1 เพียงอย่างเดียวไม่แทน confidence requirement
- Minimum 100 trades และ 30 active days ต่อชุดที่เคยเสนอ ยังไม่ใช่ข้อตกลงที่ยืนยัน จึงห้ามใช้เป็นเกณฑ์ตายตัวโดยอ้างว่าเจ้าของเลือกไว้; sample sufficiency ต้องมีเหตุผลใน frozen protocol และยอมรับ INCONCLUSIVE
- Fibonacci/OTE analysis เป็น exploratory ใน development; หากเลือกใช้เป็น filter ภายหลังให้สร้าง strategy version และใช้ fresh holdout ไม่ใช้ผลแบ่งกลุ่มย้อนหลังเป็น confirmation ของตัวเอง
- Publication ของ spec อนุญาตงานตามขอบเขตนี้ ไม่ใช่การสั่ง deploy, เปลี่ยน credentials หรือเปิด real-money trading

## Testing Decisions

### จุดทดสอบหลัก

ใช้ behavioral seam ที่ระดับ orchestration/engine: ป้อน market/account/broker/clock event stream ที่กำหนดลำดับได้ แล้วตรวจ externally observable decisions, adapter requests, ledger, risk state และ notification payloads ใช้ detector และ risk logic จริงภายใน ไม่ mock สิ่งที่กำลังพิสูจน์

ใช้ in-memory broker/notification adapters ที่จำลอง reply/event ordering ได้เพื่อไม่ส่งคำสั่งหรือข้อความจริงใน unit tests เพิ่ม targeted unit tests เฉพาะ pure numerical boundaries เช่น fractal confirmation, Fibonacci orientation และ lot-step normalization รวมถึง broker mapping contract tests ที่จำเป็น

มีการส่ง seam นี้ให้ผู้ใช้ตรวจระหว่าง synthesis; หากไม่มีคำแก้ไขก่อนเผยแพร่ ให้ถือเป็น engineering recommendation ไม่อ้างว่าได้รับการยืนยันแล้ว

### Prior art และ regression strategy

- ใช้ unittest framework และ seams ของ detector/orchestrator/backtester/adapter/notifier ที่มีอยู่ต่อ ไม่เพิ่ม test framework โดยไม่มีเหตุผล
- Existing orchestrator tests มี fill-bar stop-out case; ต้องยกระดับให้ตรวจ trade ledger และ summary ด้วย เพราะสถานะภายในถูกไม่ได้แปลว่า backtest บันทึกครบ
- Existing spread-guard test ยืนยันการข้าม fill เมื่อ spread สูง ต้องแทน expectation นี้ใน broker lifecycle tests ด้วย authoritative fill/cancel semantics
- Existing detector happy path ไม่พิสูจน์ CHoCH เพราะไม่มีโครงสร้าง HH/HL/LH/LL และ protected-swing classification ต้องเพิ่ม negative examples ที่แยก continuation, internal break และ reversal
- เขียน failing reproductions ที่ observable seam ก่อนแก้ production behavior ตามกติกา repository ไม่เพิ่ม tests ที่เพียงคัดลอก implementation

### Required scenarios

1. BUY และ SELL: H1 bias อนุญาต แต่ M5 เป็น BOS หรือยังไม่มี CHoCH ต้องไม่ส่ง entry
2. Protected swing เทียบ internal swing: minor break ไม่ถูกเลื่อนเป็น CHoCH; wick-only breach ไม่ผ่าน body-close confirmation
3. UNKNOWN/RANGE, equal highs/lows และ swing ที่ยังไม่ confirmed ให้ผลตรงกับ frozen structure contract
4. Future-append/mutation และ replay-prefix equivalence: decisions ก่อนเวลาที่แก้ต้องเหมือนเดิม รวม EMA, fractals, pool availability และ Fibonacci features
5. Sweep-to-MSS boundary 8 bars, FVG middle boundary 4 bars และ right-candle close; ไม่มี order หรือ fill ก่อน confirmation
6. Displacement/body-ratio boundaries, zero-range candle, FVG minimum gap, BUY/SELL FVG orientation และ glossary/code agreement
7. Pool ที่ยังไม่ available, pool ที่ consumed, previous-day coverage หาย, nearest R ต่ำกว่า 1.5 และ tick rounding ทำให้ R หลุดเกณฑ์
8. Setup replay ซ้ำ, invalidation ก่อน submission, TTL expiry และ restart หลัง expiry ต้องไม่สร้าง fresh order จาก setup เดิม
9. Fibonacci BUY/SELL orientation, anchor availability, zero-width range และ 62%/79% boundaries; OTE tag ต้องไม่เปลี่ยน admission decision ใน baseline
10. Minimum volume over budget ต้อง skip; volume rounding down, actual balance/equity, metadata/point conversion และ missing margin information
11. Manual loss events เปลี่ยน whole-account daily gate แต่ไม่เพิ่ม bot trade PnL; incomplete account events ห้ามอ้าง parity หรือ reset risk
12. Account-mode/ownership isolation: cancel/close request ระบุเฉพาะ bot-owned exposure และไม่จัดการ order จาก symbol match อย่างเดียว
13. Accept/reject/UNKNOWN, timeout แล้วพบ order อยู่จริง, duplicate broker events และ restart หลังส่งก่อนบันทึก response ต้องไม่เปิดซ้ำ
14. Fill ก่อน cancel acknowledgement, partial fill พร้อม residual, expiry ขณะ disconnect และ late broker events ต้อง reconcile ได้โดยไม่ลบ exposure
15. Spread สูงหลัง pending accepted ไม่ทำให้ actual fill หาย; news/TTL/risk cancellation ใช้ lifecycle เดียวกัน
16. Fill แล้ว SL ใน tick/แท่งเดียว, SL กับ TP ในแท่งเดียวแต่ tick ordering ต่างกัน และ TIME_EXIT ที่กำไร/ขาดทุน/เสมอ ต้องถูกนับครบ
17. Daily UTC boundary, two net losing trades, daily equity threshold และ 5% high-water drawdown; restart ไม่ล้าง halt และไม่ reset เพราะ history ไม่พร้อม
18. News blackout boundaries, revised/stale/missing schedule, pending cancellation และ position ที่ถือผ่านข่าวโดยไม่มี pre-news BE/forced exit
19. Time-exit clock ขณะไม่มี bar ใหม่, broker close rejection และ reconnection; ไม่มีแจ้งว่าปิดแล้วก่อนมีหลักฐาน
20. Order accepted message แยกจาก fill message; rejected/UNKNOWN intent ไม่ส่ง phantom trade และ notification failure ไม่ก่อ duplicate order
21. Cost accounting ไม่หัก spread ซ้ำ, fees/partial deals aggregate ถูก, R denominator ตรึง และ operating-cost loss ไม่ถูกซ่อนด้วย positive expectancy
22. Dataset gap/ambiguous order/provenance mismatch ให้ DATA_INSUFFICIENT แทน PASS; few trades ให้ INCONCLUSIVE โดยไม่เปลี่ยนกฎ
23. Statistical protocol fixtures ให้ผลคงที่ตาม one-/two-sided choice และ dependence assumptions; stress outcomes ไม่ถูกเลือกย้อนหลังให้ผ่าน
24. Oracle smoke/soak/restart/reconnect และ Mac-off verification ใช้ Demo ที่ตรวจ identity แล้ว; failure report แยก infrastructure defect จาก strategy loss

ตรวจ dependency/runtime compatibility ตาม environment ที่ใช้จริง, รัน unit suite ของ repository และ MT5 connectivity smoke test เมื่อแก้ connector/symbol/timeframe จากนั้นจึงตรวจ Demo end-to-end ไม่ถือว่า mocks หรือ dry-run ผ่านแทน broker verification

## Out of Scope

- Real-money deployment, การเปลี่ยน credentials/permissions, การอัปเดตหรือ reboot VM และการส่งคำสั่งซื้อขายในระหว่างงานเขียน spec นี้
- Profit guarantee, การรับรอง win rate จากชื่อเทคนิค, การตั้งรายได้รายวัน/รายเดือน หรือ quota เพื่อบังคับให้มี trades
- Martingale, grid, averaging down, minimum-lot risk override และการบีบ SL เพื่อให้เปิด position ได้
- Partial profit-taking, automatic breakeven และ pre-news forced exit ใน baseline
- การเพิ่ม Fibonacci/OTE เป็น entry filter, เปลี่ยน entry ไป Fib level หรือเปลี่ยน TP เป็น Fibonacci extension โดยอัตโนมัติ
- Order Block, breaker block, OTE optimization, extra indicators, machine learning, multi-strategy portfolio และ parameter search ที่ไม่ได้ลงทะเบียนเป็น experiment
- Pine/TradingView parity, UI redesign และ Google Sheets feature expansion ก่อน core correctness และ Demo evidence
- Paid execution infrastructure หรือ migration ไป platform อื่นโดยไม่มี decision แยกเมื่อ Oracle experiment ไม่ผ่าน
- การลบหรือแก้ประวัติ ADR ให้ดูเหมือนกฎล่าสุดเป็นสิ่งที่ตกลงไว้ตั้งแต่แรก

## Further Notes

### Material decisions ที่ยังไม่ settled

Issue นี้รวบรวมงานที่เริ่มได้ทันทีและระบุ gates สำหรับส่วนที่ยังต้องปิดนิยาม Label ready-for-agent ไม่ได้หมายความว่า logic ทุกตัวถูกยืนยันแล้ว, สามารถ freeze profitability experiment ได้ทันที หรือพร้อมใช้เงินจริง Agent เริ่ม reproductions, data feasibility และ core contracts ที่ settled ได้ แต่ห้ามเลือก material trading policies ต่อไปนี้เงียบ ๆ:

| เรื่อง | สิ่งที่ตกลงแล้ว | สิ่งที่ต้องล็อกก่อนส่วนที่เกี่ยวข้อง |
| --- | --- | --- |
| Protected swing / CHoCH | M5 CHoCH เป็นเงื่อนไขเข้า; latest fractal อย่างเดียวไม่พอ | วิธีสร้าง HH/HL/LH/LL, เลือก protected swing, internal/external scope, initialization, ties และ recovery หลัง structural break |
| MSS qualification | ต้องมี displacement qualification และ FVG | CHoCH break candle ต้องผ่าน body ratio ในแท่งเดียวหรือไม่; handling weak first break; ห้ามเพิ่ม volatility threshold โดยอ้างว่าตกลงแล้ว |
| Sweep / pool lifecycle | Wick rejection, known pool, untouched TP selection | exact touch quote side, repeated sweep/consumption, setup invalidation และข้อเสนอ cancel เมื่อ TP ถูกแตะก่อน fill ซึ่งยังไม่ได้รับการยืนยัน |
| Fibonacci anchors | เก็บค่าเท่านั้น; OTE 62–79% | ขาราคาและ anchor-selection rule, freeze time; ห้ามเลือก final swing จากอนาคตหรือเลื่อน anchors ย้อนหลัง |
| Pending/session timing | TTL 4 M5 bars; session admission windows | exact TTL origin, endpoint inclusivity, handling session end, server-side expiry capability และ cancellation latency model |
| Account risk accounting | 0.5% ต่อ trade, daily 2 losses/1%, DD 5%, whole account | min(balance,equity) proposal, partial/manual loss aggregation, open-risk budget, cash flows/credit, daily-halt disposition ของ positions และ manual position ไม่มี SL policy |
| Cash flows / intervention | ต้องแยกจาก bot edge และเปิดเผยผล | pause/rebase policy สำหรับ deposit/withdrawal/credit; ข้อเสนอ pause ยังไม่ถือเป็น user-confirmed behavior |
| Data provenance | M5/H1/ticks และ historical USD HIGH news | source coverage, feed reconciliation tolerance, point-in-time news availability และ acceptance ของ proxy feed |
| Statistical protocol | 95% lower bounds, net expectancy positive, win probability over 50%, no quota | one-sided versus two-sided, block bootstrap details/dependence/coverage, sample sufficiency, dollar/R denominators, stress magnitudes และ fixed evaluation dates |

ผลของการปิดนิยามต้องบันทึกเป็น versioned decisions พร้อม behavioral examples ก่อนเริ่มใช้ข้อมูลประเมินเลือกกฎ การมีช่องว่างเหล่านี้ไม่อนุญาตให้กลับไปใช้ known-broken semantics เพื่อให้งานดูเสร็จ

### Evidence ที่มี และที่ยังไม่มี

- Review ในบทสนทนานี้รัน unit suite ได้ 53 tests ผ่าน และมี synthetic reproductions ของ fill-bar accounting, SL/TP inconsistency, spread fill suppression และ premature pending-state removal ผลนี้เป็นหลักฐานของ software behavior เท่านั้น
- ยังไม่มี verified Exness account specification, live broker reconciliation, Oracle emulation success หรือ 12-month M5/tick/news profitability result จากงานนี้
- ข้อมูลสเปก VM มาจาก output ที่ผู้ใช้ให้ ไม่ใช่ remote inspection ในงานนี้
- ไม่เผยแพร่ broker credentials, account login, SSH endpoints หรือ secrets ใน spec
- Issue tracker ที่ตรวจพบคือ GitHub Issues ของ Piti9427/XAUUSD_Scalper; ใช้ label ready-for-agent ตามคำสั่ง to-spec

### แหล่งอ้างอิงประกอบข้อจำกัด

- [Exness XAUUSD contract specification](https://get.exness.help/hc/en-us/articles/17854173039388-Commodities) — สเปกทั่วไปต้องตรวจซ้ำกับบัญชีและ symbol ที่เชื่อมต่อ
- [Exness tick history](https://get.exness.help/hc/en-us/articles/360021547851-Tick-history) — tick provenance และข้อจำกัดการเลือก trading server
- [MT5 order properties](https://www.mql5.com/en/docs/constants/tradingconstants/orderproperties) — accepted, partial, filled, cancel-request และ expiry states
- [NIST confidence intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm) — one-sided และ two-sided confidence bounds ต่างกัน
- [Fidelity Fibonacci retracement](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/fibonacci-retracement) — retracement อ้างอิงช่วง swing
- [OTE educational definition](https://howtotrade.com/wp-content/uploads/2024/05/Optimal-Trade-Entry-in-ICT.pdf) — ที่มาของ research zone 62–79%; ไม่ใช่หลักฐาน profitability ของ baseline

Spec นี้สังเคราะห์ข้อตกลงและ review ถึงวันที่ 2026-09-08; การเผยแพร่ไม่ใช่การรับรองว่า implementation หรือ validation ที่อธิบายไว้เสร็จแล้ว
