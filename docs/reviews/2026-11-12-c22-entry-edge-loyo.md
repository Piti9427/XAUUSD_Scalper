# New entry edge research: LOYO verdict (2026-11-12)

**Goal:** find an entry edge that stops 26b8's range years (2020–2024a) from losing.

**Method:**
- Protocol `runs/c22-entry-edge-2026-11-12/protocol.json` (sha256 `8b3b379a…0083`), frozen before the runs.
- 34 specs, each run on 7 yearly $313 accounts, base+swap and stress+swap.
- Selection is leave-one-year-out (LOYO), as in [2026-11-12-c22-regime-fix-loyo](2026-11-12-c22-regime-fix-loyo.md).
- Every spec uses the unchanged 26b8 execution path: ATR stop, RR target, BE, caps, daily rules, 0.01 lot, costs and swap.
- Engine: `eng.py` swaps `frame.direction` only. Parity with native holds exactly, and pool cells match in-process reruns (6/6 spot checks).

## Standalone families: no edge

| Family | Variants | Best 7-year stress sum | Notes |
| --- | --- | --- | --- |
| RSI7 fade, weak H4 trend (mr) | 8 | −708 | Loses in 5–7 of 7 years |
| Bollinger re-entry fade (bbf) | 8 | −482 | Wins only 2024a and sometimes 2024b25 |
| H4-aligned EMA50 pullback (pb) | 4 | −1,212 | Worst family |
| London opening-range breakout (orb) | 4 | −481 | Positive only in 2024b25 |

None of the textbook families is profitable on its own, in any regime, with these costs.

## Union (26b8 first, RSI7 fade fills empty bars) + B2 + maxloss_1

The frozen outer gate **passes**:
- LOYO picked `B2ml+native+mr30_s0.3` in 6 of 7 folds. The 2024b25 fold had no passing candidate and kept native.
- Held-out sums:

  | | native | B2+maxloss_1 | pick |
  | --- | --- | --- | --- |
  | Base | 1,097 | 1,378 | **1,568** |
  | Stress | 390 | 711 | **852** |
  | Range years (base) | −696 | −304 | **+35** |

- Held-out wins against native: 4 of 7.

**Root cause (attribution in `attrib.json`) says this is not an entry edge:**
- The RSI-fade trades themselves earn −$26 base and **−$374 stress** across the five range years.
- The gain comes from **displacement**. Fade trades take the single position and trigger maxloss_1, which blocks native trades that would have lost (+$323 base in range years).
- In effect it is an indirect "trade less on weak-trend days" throttle, and a costly one under stress.
- It is fragile to parameters. The neighbouring `s0.6` variants collapse to −65 / −219 stress.
- It is worse on the forward window 2026-10-24..11-11:

  | Account / view | B2+maxloss_1 | pick |
  | --- | --- | --- |
  | $313 base | +48.01 | +41.99 |
  | $1,845 base | +48.01 | +27.74 |

## Verdict

- **No new entry edge was found.** Do not adopt the union. It passes the gate by accident of mechanism, and the forward window is already worse.
- `B2+maxloss_1` stays the only candidate.
- A possible next direction (not run): test the displacement mechanism directly as a day-level throttle that blocks native entries for the day after a weak-trend condition, with no fade trades. It needs a new protocol and would face the same overfit risk as the v1 entry filters that already failed.
- Limits: all history has been seen. The families are textbook choices, not mined from this data, but were picked after seeing all the years. Real money stays prohibited.
