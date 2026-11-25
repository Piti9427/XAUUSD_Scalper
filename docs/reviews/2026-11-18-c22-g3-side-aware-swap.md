# G3: side-aware swap check at admission. Prepared, NOT deployed (2026-11-18 → 21)

## Why
The live-vs-model comparison (`2026-11-18-c22-live-vs-model-defects.md`) found that **10 of the 13 missed model trades** came from one cause: `cost_spec_mismatch` on `swap_long` while the signal was a **SELL**.
- A SELL pays `swap_short`, which is stored as 0.0. It never pays `swap_long`.
- The admission check compared the whole spec, so BUY-side swap drift blocked SELL entries:

| Date | Broker `swap_long` |
|---|---|
| 10-30 | −488 |
| 11-03 | −481 |
| 11-13 | −475 |
| 11-16 | −471.7 |

## Change
Workspace: `runs/c22-g3-2026-11-18/`.
- `base/` is a byte copy of live release 6d7b.
- `repo/` is the patched copy.
- `g3.patch` is the diff. `SHA256SUMS` hashes the patch and the test.

| File | Change |
|---|---|
| `scripts/demo_runtime/costs.py` | `swap_fields_not_paid_by(direction)` returns `("swap_long",)` for SELL and `("swap_short",)` for BUY. `validate_policy`/`validate_evidence` gain `ignore_swap_fields=()`. It accepts only one of `swap_long` or `swap_short` and raises on anything else. The field is still read from the broker, so read failures still fail closed. Default `()` keeps the old check for every other caller (review, renewal, status, readiness, generations). |
| `scripts/demo_runtime/admission.py` | Admission passes `ignore_swap_fields=swap_fields_not_paid_by(direction)`. |

**Unchanged:**
- The paying side's swap stays exact for a stored 0.0, and banded otherwise.
- Every other spec field stays exact.
- Policy expiry, account, tariff, calendar and observed-cost audit.
- Cap, lot, SL/TP, strategy.
- Renewal tooling, which still requires the broker spec to equal the approved policy.

## Verification (Mac)
- **New test** `test_g3_side_swap.py` (9 tests). It uses the **real live v4 policy** and the **real 18 Nov broker probe spec**.
  - Patched copy: **9/9 OK**.
  - Live 6d7b copy: 13 red results (12 errors + 1 failure) for the missing feature. Its regression tests stay green: the live spec passes, and a default call still blocks drift.
- **Covered cases:**
  - SELL passes with `swap_long` at −675, −644.8, −100 and +50.
  - SELL still blocks a `swap_short` change.
  - BUY still blocks `swap_long` drift.
  - `trade_tick_size`, contract size, `swap_mode` and `swap_rollover3days` stay exact.
  - An expired policy still blocks.
  - Bad arguments raise.
  - Admission wiring is present.
- **Differential** `tests/demo` (unittest discover, 303 tests) on 6d7b vs patched: **same 45 pre-existing failures, 0 new, 0 fixed**. The failures come from Mac tests drifting from the VM release, as already listed in handoff I7.

## Release impact
- `costs.py` and `admission.py` are **not** in `config/c22-selected-demo.json` `source_hashes` (25 pins), so there is no `source_drift` risk. The 70b1 incident was a pinned-file edit.
- The cohort changes:

  | | release_hash | config_hash |
  |---|---|---|
  | Current (6d7b) | `6d7b9c46…` | `df6a716a…` |
  | With G3 | `e09853cb…` | unchanged |

  This needs a **code-only review deploy** through `go-deploy.sh` (as D8), while flat and outside the forbidden windows. The cost policy (v4) is unchanged.
- **Interaction with renewal v5:**
  - If G3 deploys first, regenerate `expected-cohort.json` in `state/staging-renew-v5-20261118` for the new release before renewing.
  - Renewal itself is unaffected: it is still exact-swap, owner-approved and G2-guarded.
- **Observability trade-off:**
  - SELL entries no longer surface `swap_long` drift through the gate, so neither G1 nor the G2 harvest sees it from SELL signals.
  - BUY signals and renewal probes still do.
  - If wanted, a later non-blocking audit line could log ignored drift. It is not included, to keep the diff minimal.

## Expected effect
- In the 10-24..11-16 window, G3 would have let the 10 swap-gate SELLs through. In the model those 10 net to **−2.49**: 5 TP and 5 SL.
- G3 does **not** promise more profit. It makes live trading match the tested native strategy, so its results stop depending on swap drift luck.
