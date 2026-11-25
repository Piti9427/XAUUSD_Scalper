# Losing-years pause research: verdict (2026-11-12)

- Spec: `docs/superpowers/specs/2026-11-12-c22-losing-years-pause-design.md`
- Plan: `docs/superpowers/plans/2026-11-12-c22-losing-years-pause.md`
- Code and results: `runs/c22-pause-2026-11-12/`. The ledger is in `progress.md`. Tests: `test_pause.py`, 9/9 OK. Parity holds in 14/14 cells.

## Frozen v1 (protocol `e7680dc2…12e0`): **FAIL**

- Catalog: 39 specs, LOYO on yearly $200 accounts against the base B2+maxloss_1.
- LOYO picked `B_L10` (weekly side gate) in 6 of 7 folds.

| | base | held-out pick |
| --- | --- | --- |
| Sum, base view | 812 | 1,000 (c1 ✓) |
| Sum, stress view | 331 | 519 (c1 ✓) |

| Criterion | Result | Detail |
| --- | --- | --- |
| c2: each range year ≥ −$10 | ✗ | 2020 −78, 2021 −104, 2023 −37 |
| c3: trend years ≥ 85% of base | ✓ | |
| c4: survival | ✗ | Continuous $200 from 2020 cap-locked for 401 days and ended at $16.6 |

**Root cause (`attrib.json`):**
- **A (pause) works only where losses persist.** In 2020 it went from −92 to −20 and in 2021 from −104 to +7. In 2023 and 2024a the shadow curve alternates, so pausing removes winners about as often as losers (2023: 95 trades removed, net only −$12).
- **The $200 cap is structural.** In 2026 the median risk of a 0.01-lot trade is $23–26, which is above the 10% cap of $20. So the $200 base gets 392 `risk_cap` rejections in 2026 and makes +41, against +763 at $313.
- `B_L10`'s 2026 gain (+656) is path-dependent headroom; `B_L20` makes −1.6 the same year.

## Derived v1b (protocol `15c58165…0a42`): **FAIL**

- Change tested: a tighter ATR stop (1.5 or 2.0) to fit under the $200 cap.
- Result: worse everywhere. Cost per R goes up and stop-outs become more frequent, which is mechanism 3 of the diagnosis.
- The iteration budget is used up.

## Owner request: risk cap above 10% (research only, `caps.py`)

Continuous accounts from 2020 to 2026-10, fixed 0.01 lot, ending balance:

| Mechanism | cap 10% $200 base / stress | cap 12.5–20% $200 base / stress |
| --- | --- | --- |
| base (B2+maxloss_1) | $17 / $17 (locked) | $8–13 / $7–14 (locked, dies **faster**) |
| A `n20_k2_r2` | $1,616 / $842 | $1,446–1,695 / **$22–42 (dies)** |
| B `L10` | $17 / $19 (locked) | $9–13 / $9–13 |
| AB `n20_k2_r2_L10` | **$1,680 / $1,207** (DD 34% / 58%) | the same or slightly lower |

**Raising the cap does not help and often hurts.** It admits trades with a larger stop at a low balance, so the account loses faster in range years. This repeats the 2026-09-29 lesson in AGENTS.md. Keep 10%.

## Main finding (descriptive, not a pass)

The AB family survives a continuous $200 account from 2020 in most of its parameter neighbourhood, when the resume rule needs a +2R recovery (r = 2):

| | Base view survives | Stress view survives |
| --- | --- | --- |
| AB, r = 2 | 11 / 12 | 10 / 12 |
| base B2+maxloss_1 | dies | dies |
| A alone, r = 2 | 5 / 6 | 1 / 6 |

Example, `AB_n20_k2_r2_L10` at $200:

| | Value |
| --- | --- |
| Base final | $1,680 |
| Base yearly | +19.5, +17.9, +131, −31.7, −30.4, +891, +482 |
| Stress final | $1,207 |
| Min equity | $165 |

Even so, the yearly c2 bar still fails in 2023 and 2024a (−$31 / −$30), and this family was identified *after* the frozen LOYO failed. It is a candidate for a **new frozen protocol and forward observation**, not for adoption.

The forward window (2026-10-24..11-11) at $200 is −46 for every spec: the cap rejects the large 2026-size stops. At $313 it is +48.

## AB r2 re-test against the deployed bot (protocol `2fad11f9…6115`): **FAIL**

Owner goal: the tuned variant must beat the bot running on the VM, native 26b8.

- **Catalog:** 12 AB specs with r = 2 (pause resumes only after +2R), against native at $313 and $200.
- **Engine fix applied first:** the pause state now carries across segments. Test suite 10/10.
- **Result:** LOYO keeps **native in every fold** at both balances, so the verdict is FAIL. The T2 continuous paths are therefore identical to native.

Why AB fails the gate. Example `AB_n20_k2_r2_L10` at $313 over 7 years:

| | AB | native |
| --- | --- | --- |
| Mean $/month, base | 17.97 | 13.89 |
| Mean $/month, stress | 13.11 | 4.93 |
| Losing months | 22 | 41 |
| Worst month | better | — |
| % profitable months, base | 40.5% | 46.8% |

- AB fails only the frozen "% profitable months ≥ native" criterion. 25 of its 79 months are flat because trading is paused, and a flat month counts as not profitable.
- It would still fail the trend criterion. In 2026 AB makes **$417 against native's $887**, a −53% give-up in the regime the VM is trading now.
- Attribution of the 2026 give-up: each protective layer removes SELL winners.
  - maxloss_1 costs −$340 on SELL.
  - The weekly gate costs −$120 to −$400 on SELL.
  - The pause costs about −$100.
- Forward window 2026-10-24..11-11: identical to native (+48.01 at $313; −46.23 at $200).

**Conclusion for "better than the bot on the VM":**
- AB wins on the 7-year total, mainly because the range years lose less.
- It **loses in the current trend/high-volatility regime (2026)**, which is what the VM is trading now.
- No variant beats the deployed bot under the frozen protocol.

## Recommendation

1. Keep the 10% cap. Do not raise it.
2. $200 is structurally too small for 2026-level volatility. A single 0.01-lot stop is larger than 10% of $200. Stay at about $313 or more.
3. If you want to pursue it: freeze a new protocol for the AB r = 2 family, judged on survival of the continuous account plus range-year loss, then run a forward observation of AB_n20_k2_r2_L10 on Demo. This needs runtime work: a new RulesID, a live shadow stream, the weekly gate, and owner approval.
