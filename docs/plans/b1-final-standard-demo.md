# Implementation Plan — B1 Final / Standard Demo

**Date:** 2026-09-27
**Status:** approved planning baseline; implementation not started by this document task
**PRD:** [Finalize B1 for Standard Demo](../specs/b1-final-standard-demo-prd.md)
**Tickets:** [Dependency index](../../.scratch/b1-final-standard-demo/README.md)

## Outcome

ส่งมอบ executable B1 EA สำหรับ MT5 Tester พร้อม execution/recovery/risk/notification validation และ frozen release package ใช้ Standard Demo จาก local environment เป็นบัญชีเป้าหมาย ส่วนเงินจริงและการเปิดส่ง Demo orders ไม่ได้รับอนุญาตจากการจัดทำเอกสาร

## Frozen defaults

- B1 เดิม: M15, Donchian30, RSI14 75/25, SL 2.5ATR, TP 3.5R, maximum one position.
- Risk tiers 1/0.75/0.5/0.25%; equity-HWM DD >=12% latches stop-new-entries.
- ใช้ actual Demo equity ใน account-constrained run; $100 เป็น hypothetical scenario แยก ห้ามแทนที่ broker balance.
- เป้าหมาย Standard Demo supersedes Cent. Verify credentials/identity privately; no credentials or account numbers in these artifacts.
- Original frozen version remains intact. Only proposed strategy adjustment is one-shot cost-covering SL after +2R in a separate version.

## Execution path

Completed UTC M15 data -> canonical B1 detection -> signal expiry -> account/risk/volume/margin/geometry gates -> market request with SL/TP -> broker transaction reconciliation -> persisted exposure and HWM -> confirmed execution outbox -> notification sink.

รับ actual fill แล้วตรึง position R จาก fill ถึง original SL โดยเก็บ intended quote R แยก SL/TP เริ่มต้นไม่ re-anchor ตาม fill; reference และ EA ต้องใช้ semantics เดียวกันเมื่อเปรียบเทียบ

Use existing deterministic indicator core and Python oracle. The new B1 EA does not replace or run concurrently as another owner of the existing SMC execution path. Default order permission is Tester-only.

## Delivery sequence

| Ticket | Deliverable | Blocked by |
|---|---|---|
| 01 | Verified Standard Demo target and affordability report | None |
| 02 | Reference/MQL5 parity evidence | None |
| 03 | Complete protected baseline trade in Tester | 01, 02 |
| 04 | Timeout, partial-fill and restart recovery | 03 |
| 05 | Persistent HWM, risk tiers and incident protection | 03 |
| 06 | Confirmed +2R cost-covering stop lifecycle | 04, 05 |
| 07 | Broker-confirmed event notifications | 03 |
| 08 | Exit selection and frozen release package | 04, 05, 06, 07 |

Start with 01 and 02. After 03, tickets 04, 05 and 07 are independent work frontiers; this is sequencing information, not authorization to spawn agents.

## Safety and failure behavior

- Floor lot sizes; fail closed on missing account/spec/time/state evidence. Never squeeze SL or raise risk to admit a trade.
- Timeout -> reconcile before any resubmission. Definitive entry rejection ends the attempt for that signal.
- Partial fill -> retain accepted volume, reconcile/cancel outstanding remainder; no automatic top-up.
- Missing protective SL or actual-fill risk above budget -> close only owned B1 exposure, latch incident halt; failed close remains critical and blocks entries.
- Restart -> read broker exposure, validate persisted HWM and request/exit state, reconcile, then consider enabling new entries. Missing HWM is not reconstructed optimistically from current equity.
- Foreign exposure is never closed. Duplicate ownership blocks new risk.
- SL modification remains pending until broker confirms. Definitive rejection retains old SL and ends the one-shot attempt; uncertain result requires reconciliation.
- Notification delivery cannot control execution. External delivery timeout may remain uncertain even with local event deduplication.

## Validation and finalization

Test externally visible full lifecycles, first reproducing incorrect behavior before production-code fixes. Compare indicators/signals and intended trades on identical inputs, then execute real-tick Tester runs and reconcile broker outcomes.

For exit selection, preserve chronological state and report all saved losers, displaced winners and changed subsequent entries. At both 0.10R/0.20R sensitivity reserves, cost-covering exit must exceed baseline in total net R and return, remain net-positive with PF >1, keep DD no worse and <12%, avoid hard stop and outperform in >=2/3 chronological blocks. Stress scenarios must retain positive net profit above baseline and pass DD constraints. Unknown actual costs remain an open qualification gate.

If exit fails, freeze fixed-exit build with BE disabled. If actual account admits no trades, report ACCOUNT_BLOCKED; synthetic Tester fixtures and fractional research do not qualify that account. If baseline profitability fails, report STRATEGY_NO_GO even when EA behavior is correct.

Final evidence: source/build/config/data/spec hashes; sanitized preflight; reference parity; actual Tester report/deal ledger; request/position/recovery/modification logs; net-PnL/equity reconciliation; stress comparison; start/stop/recovery runbook; separate implementation, strategy, account and deployment verdicts.

## Current evidence boundary

These files document approved work; no implementation, broker connection, compilation, Tester run or order submission occurred as part of generating them. Prior handoff test figures remain historical evidence, not freshly executed checks.
