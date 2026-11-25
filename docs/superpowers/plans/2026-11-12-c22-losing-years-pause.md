# C22 losing-years pause: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Research-test an equity-curve pause (A) and a weekly side gate (B) on B2+maxloss_1. Judge them by LOYO on $200 yearly accounts, plus a continuous $200 survival run and the forward window.

**Architecture:** A small research package in `runs/c22-pause-2026-11-12/` (gitignored), layered on the composed engine `runs/c22-26b8-tuning-loop-2026-11-11/loopeng.py`:
- `shadow.py` builds the per-tape shadow trade stream.
- `pause.py` holds the pause state machine.
- `weekly.py` holds the W1 side gate.
- `eng.py` wires both into the replay via `X['gate']`.
- `run.py` executes the frozen protocol.

**Tech Stack:** Python 3.14, numpy, pandas, multiprocessing (spawn, Pool(2)), unittest. Run everything with `PYTHONPATH=/Users/nopparuj/my-agents/XAUUSD_Scalper`.

**Spec:** `docs/superpowers/specs/2026-11-12-c22-losing-years-pause-design.md`

## Global Constraints
- Research only. No runtime, config or VM change. Real money PROHIBITED.
- The base is B2+maxloss_1 = `{'tickbe': (1.0, 5, 1), 'max_daily_losses': 1}`. Native rules, 10% cap, 0.01 lot and costs+swap are unchanged.
- Views are `base` and `stress`. Swap is always on (`F.SWAP`).
- Segments: 2020, 2021, 2022, 2023, 2024a, 2024b25, 2026 (`loopeng.SEGMENTS`). LOYO accounts each start at **$200**.
- Catalog of 39 specs:
  - base;
  - A: N ∈ {10, 20, 30} × k ∈ {2, 4} × r ∈ {0, 2};
  - B: L ∈ {10, 20};
  - A×B: 24.
- Freeze `protocol.json` and record its sha256 before any catalog run. Use Pool(2) and run the low-disk guard (kill below 150 MB free).
- Do not commit. `runs/` is gitignored, and the owner commits docs on request.

## Review Focus
1. **Shadow self-lock.** A $200 shadow would cap-lock and stop producing trades, so the pause could never resume. Decision: run the shadow at a $10,000 balance (cap never binds). R = net/risk_usd is lot-independent at 0.01. Test `test_shadow_uncapped_keeps_trading_after_drawdown`.
2. **Look-ahead on the shadow.** A shadow trade that exits at exactly the decision ms must not count. Test `test_exit_at_decision_time_not_counted`.
3. **Look-ahead on the weekly bar.** The current, unfinished week must never be used. Test `test_weekly_uses_only_closed_weeks`.
4. **Warm-up.** No pause can trigger before N shadow trades have closed on the tape. Test `test_no_pause_before_n_trades`.
5. **Parity.** k = ∞ with no B must reproduce the base exactly in all 14 cells. Test `test_parity_with_base` (one cell in unit tests; all 14 in `run.py` before the catalog).

---

### Task 1: Shadow stream + pause state machine

**Files:**
- Create: `runs/c22-pause-2026-11-12/shadow.py`, `runs/c22-pause-2026-11-12/pause.py`
- Test: `runs/c22-pause-2026-11-12/test_pause.py`

**Interfaces:**
- Produces:
  - `shadow.stream(tape: str, view: str) -> tuple[np.ndarray, np.ndarray]`: `(exit_ms int64 sorted, r float64)` for the base spec run over the whole tape at `SHADOW_BAL = 10000.0`. Cached on disk at `cells/shadow-{tape}-{view}.npz`.
  - `pause.PauseState(exit_ms, r, n: int, k: float, resume: float)` with `.paused(ms: int) -> bool`. Calls are made in non-decreasing ms order.

Algorithm for `.paused`:
- `i = searchsorted(exit_ms, ms, side='left')`.
- If `i < n`, return False.
- `s = r[i-n:i].sum()`.
- If not paused and `s < -k`, set paused.
- Else if paused and `s >= resume`, clear paused.
- Return the paused state.

- [ ] **Step 1: Write failing tests** in `test_pause.py`:
  - `test_no_pause_before_n_trades`: exit_ms = [1, 2], r = [-5, -5], n = 3, k = 2 → `.paused(10)` is False.
  - `test_exit_at_decision_time_not_counted`: exit_ms = [1, 2, 3], r = [-1, -1, -1], n = 3, k = 2 → `.paused(3)` is False and `.paused(4)` is True.
  - `test_hysteresis`: r = [-1, -1, -1, +1, +1], exit_ms = [1, 2, 3, 4, 5], n = 3, k = 2, resume = 0. Assert this sequence:

    | Call | Window | Sum | Result |
    | --- | --- | --- | --- |
    | `.paused(4)` | r[0:3] | −3 | True (pauses) |
    | `.paused(5)` | r[1:4] | −1 | True (−1 < resume) |
    | `.paused(6)` | r[2:5] | +1 | False (resumes) |
  - `test_shadow_uncapped_keeps_trading_after_drawdown`: `stream('w2022', 'base')` has more trades with exit in 2021 than the $200 base ledger for 2021 run as one continuous account from 2020-01.
- [ ] **Step 2: Run** `python3 -m unittest test_pause -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** `shadow.stream` (calls `loopeng.xrun(BASE, fr, tk, view, fr.index[0], end_of_tape, SHADOW_BAL)`, where end_of_tape is the max `SEGMENTS` end for that tape) and `PauseState`.
- [ ] **Step 4: Run tests.** Expected: PASS (4 tests).

### Task 2: Weekly side gate

**Files:**
- Create: `runs/c22-pause-2026-11-12/weekly.py`
- Test: `runs/c22-pause-2026-11-12/test_pause.py` (append)

**Interfaces:**
- Produces: `weekly.side(fr: pd.DataFrame, L: int) -> pd.Series`, indexed like `fr`, values in {1, -1, 0}:
  - 1 = BUY only allowed, −1 = SELL only allowed, 0 = warm-up (both blocked).
  - Build it from `fr.close.resample('W-FRI', label='right', closed='right').last()`. Sign = close vs SMA(L) of those weekly closes.
  - A weekly value becomes visible at **label + 1 day** (Saturday 00:00 UTC), then forward-filled onto bar close times (`fr.index + 15min`).
- [ ] **Step 1: Write failing tests:**
  - `test_weekly_uses_only_closed_weeks`: on the w2022 frame, take a Wednesday bar. Its value must equal the sign computed from weekly closes whose label is at or before the previous Friday.
  - `test_weekly_warmup_blocks`: bars before L closed weeks exist give 0.
- [ ] **Step 2: Run.** Expected FAIL. **Step 3: Implement.** **Step 4: Run.** Expected PASS.

### Task 3: Engine wiring + parity

**Files:**
- Create: `runs/c22-pause-2026-11-12/eng.py`
- Test: `runs/c22-pause-2026-11-12/test_pause.py` (append)

**Interfaces:**
- Consumes: `shadow.stream`, `pause.PauseState`, `weekly.side`, and `loopeng` (`REPLAY`, `NS`, `F`, `SEGMENTS`, `TAPES`, `segment`).
- Produces:
  - `eng.xrun(spec: dict, frame, ticks, view, a, b, bal) -> dict` (the replay result).
  - `eng.segment(spec, seg, view, bal=200.) -> dict`, the same shape as `loopeng.segment`.
  - Spec keys: the base keys plus optional `pause=[n, k, resume]` and `weekly=L`.
- Approach:
  - Copy `loopeng.xrun`'s `NS['X']` setup for the base keys, with `gate = lambda d, ms, row, balance, L: 'equity_pause' if P and P.paused(ms) else ('weekly_side' if W is not None and W.get(row.Index, 0) != d else None)`.
  - Create a new `PauseState` per call, so state starts clean for each run.
  - Map the frame to its tape with an `id(frame)` lookup against `loopeng.TAPES` so the right shadow is used. For the forward tape, use `shadow.stream_frame(fr, tk, view)` on the forward input.
  - `eng.segment` mirrors `loopeng.segment` but routes through `eng.xrun` by temporarily swapping `loopeng.xrun`, as `runs/c22-26b8-regime-fix-2026-11-12/eng.py` already does.
- [ ] **Step 1: Write failing test** `test_parity_with_base`: `eng.segment({**BASE, 'pause': [20, 1e9, 0]}, '2021', 'base', 200.)['net'] == eng.segment(BASE, '2021', 'base', 200.)['net']`, and both equal `loopeng.segment(BASE, '2021', 'base', 200.)['net']`.
- [ ] **Step 2: Add test** `test_pause_blocks_entries`: with `pause=[10, 0, 1e9]` (pause as soon as 10 shadow trades sum below 0, never resume), 2021 trade count < base trade count, and the rejections include `equity_pause`.
- [ ] **Step 3: Implement. Step 4: Run all tests.** Expected: PASS.

### Task 4: Protocol, catalog run, LOYO, survival, forward

**Files:**
- Create: `runs/c22-pause-2026-11-12/protocol.json`, `runs/c22-pause-2026-11-12/run.py`, `runs/c22-pause-2026-11-12/guard.sh`

**Interfaces:**
- Consumes: `eng.segment` and `eng.xrun`.
- Produces: `result.json` with these keys:
  - `protocol_sha256`;
  - `parity` (14 bools);
  - `table` (spec → view → seg → {net, months, dd, trades, cap});
  - `folds` (held-out seg → pick, nets);
  - `criteria` (c1..c4 bools and values);
  - `survival` (view → final, cap_lock_days_max, years);
  - `forward` (spec|view|bal → net);
  - `verdict` (PASS/FAIL).
- [ ] **Step 1: Write `protocol.json`.** Copy the spec's mechanisms, the catalog names (`base`, `A_n{N}_k{k}_r{r}`, `B_L{L}`, `AB_n{N}_k{k}_r{r}_L{L}`), the inner gate, criteria c1–c4 and the forward window, verbatim from the spec. Record the sha256 with `shasum -a 256 protocol.json`.
- [ ] **Step 2: Write `run.py`.**
  - Job cache `cells/{name}-{seg}-{view}-200.json` (drop ledgers). Pool(2).
  - First assert parity of `pause=[20, 1e9, 0]` vs base in all 14 cells. Abort if any differs.
  - Then run the catalog and compute LOYO exactly as in `runs/c22-entry-edge-2026-11-12/run.py` (`gate`/`summ`), with `'base'` in place of `'native'` as the reference.
  - Criteria:
    - c1: held-out sums beat base in both views;
    - c2: every range-year held-out base net ≥ −10;
    - c3: each trend held-out base net ≥ 0.85 × base;
    - c4: survival.
  - Survival: pick on all 7 segments, run one continuous account from $200 across SEGMENTS in order with the balance carried, in both views.
    - cap_lock = the longest run of calendar days, with ≥ 1 signal, in which every non-paused, non-weekly signal is rejected by `risk_cap` and no trade is admitted.
    - Compute it from the replay `events` / rejections by timestamp. If the replay exposes only counts, add a `reject` hook through `X` that records `(ms, reason)`.
    - Pass if every run is ≤ 30 days and final > 200.
  - Forward: picks plus base on `runs/c22-forward-2026-11/input`, 2026-10-24..11-11, at $200 and $313, both views.
- [ ] **Step 3: Run** with the guard:
  ```bash
  cd runs/c22-pause-2026-11-12 && PYTHONPATH=/Users/nopparuj/my-agents/XAUUSD_Scalper nohup python3 run.py > run.log 2>&1 & nohup sh guard.sh >/dev/null 2>&1 &
  ```
  Expected: `run.log` ends with `VERDICT PASS` or `VERDICT FAIL` and `result.json` exists.

### Task 5: Root cause (if FAIL), one derived iteration, verdict doc

**Files:**
- Create: `runs/c22-pause-2026-11-12/attrib.py`; if FAIL, `protocol_b.json` and `run_b.py`.
- Create: `docs/reviews/2026-11-12-c22-losing-years-pause-verdict.md`

- [ ] **Step 1: Attribution.** Compare the all-7 pick vs base, in-process (not Pool: a known Pool-spawn attribution glitch exists).
  - Matched-trade transitions per year: paused winners vs paused losers in $ and R.
  - Days paused per year.
  - Re-entry lag in 2024b25 and 2026: days from the first base TP after a pause to the resume.
- [ ] **Step 2: If FAIL,** freeze `protocol_b.json` with one derived change that the attribution justifies, run it once, and stop.
- [ ] **Step 3: Write the verdict doc.** Include the catalog table summary, LOYO folds, c1–c4 with values, the survival path, the forward results and the root cause. State the limits (all history seen; candidate is for forward observation only).
- [ ] **Step 4: Update memory** `c22-regime-fix-loyo-2026-11-12.md` with a one-paragraph result.
