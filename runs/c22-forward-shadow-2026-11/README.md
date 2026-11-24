# C22 forward shadow (offline, research only)

Protocol v3 sha256 `15bda721c9bea40ea3992c0cd5bdac7e815fbdce2d4caf017e12c36c3299ac4d` (primary swap br474 = broker -474.3; v2 in `v2/`, v1 in `v1/`, both superseded before any verdict).
Profiles: native 26b8 / candidate sell3R_risk25.0_BE05_veto / candidate+floor0.3_both. One continuous $200 book each from 2026-10-24.

## Refresh (owner approved monthly Exness downloads 2026-11-17)
Run from this dir with `PYTHONPATH=/Users/nopparuj/my-agents/XAUUSD_Scalper`, venv `../../.venv/bin/python`.

1. Current partial month: move the old partial zip aside first, because `acquire()` skips existing files:
   `mkdir -p zips-superseded && mv zips/Exness_XAUUSDm_2026_11.zip zips-superseded/Exness_XAUUSDm_2026_11-<old last quote>.zip`
2. Download: `python -c "from pathlib import Path; from scripts.research.public_exness_archive import acquire; print(acquire(Path('zips'),'YYYY-MM'))"`
   (each month that has new data; next months like 2026-12, 2027-01 are picked up automatically).
3. `python shadow.py build`. It refuses if the previous build is not a byte prefix of the new one (data revised).
4. `python shadow.py run` writes `reports/<end>-<manifest sha12>.json`. It never overwrites.
   Verdict only when the window is ≥ 28 days AND native has ≥ 20 trades in vm490|base. Until then, INTERIM.

Never edit `shadow.py` or `protocol.json`: run() asserts hashes of every loaded engine module and input artifact.
