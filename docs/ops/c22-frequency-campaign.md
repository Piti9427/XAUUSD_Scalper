# C22 frequency research campaign

`config/c22-frequency.json` freezes 300 unique challenger variants; baseline is
additional. Only offline research, no broker or notifier entry points.

```bash
# Full fresh campaign; current month downloads into this new output directory.
python3 -m scripts.research.c22_frequency_campaign \
  --output runs/c22-frequency-2026-10-06 --workers 4

# Limit new cells this invocation. Continue later with the same output/config/runtime.
python3 -m scripts.research.c22_frequency_campaign \
  --output runs/c22-frequency-2026-10-06 --workers 4 --max-cells 20
```

Use the exact Python/NumPy/Pandas environment recorded in `search/protocol.json`
for resume. System Python and `.venv` can have different versions. Workers1–4 are
operational scheduling only; parent/config/result order remains deterministic.
`--max-cells` includes fresh finalist repeats, not the mandatory initial frozen
baseline parity check. A partial invocation cannot produce a new COMPLETE marker.
`--prepare-only` downloads/imports/freezes inputs without economic evaluation.

Each campaign has an OS writer lock, a fresh partial-month archive, original
baseline hashes, source snapshots, UTC requested cutoff and actual last quote.
The original archive and completed historical prefix remain unchanged. Resuming
reuses this campaign's frozen data: a later cutoff requires a new output directory.
No gap filling. Downloaded current-month coverage may lag the requested cutoff.

- `input/manifest.json`: input/broker/cost assumptions and content hashes.
- `search/protocol.json`: source/config/input/runtime and ordered domains.
- `search/rounds/*.json`: catalog frozen before that round's cells.
- `search/cells/*.json`: complete replay including ledger, admissions/rejections,
  equity checkpoints, all-tick DD witnesses, independent reconciliation metrics.
- `search/checkpoint.json`: hash-bound transaction and resume artifact registry.
- `search/finalists.json`, `search/repeats/*.json`: baseline/top5 full-result repeats.
- `search/results.json`: qualified ranking or NO_QUALIFIER, per-scenario gate reasons.
- Root `COMPLETE.json`: published only after repeat and final source/input checks.
- Root `BLOCKED.json`: failed integrity/metadata validation; no selected winner.

Do not modify files in a running/frozen campaign. Source/input/config drift blocks
resume; preserve old evidence and use a new campaign. A failed contender never
removes another process's completion marker. Machine artifacts are gitignored;
only synthesized Markdown belongs in `docs/reviews/`.

Every economic cell includes modeled swap. Base quoted spread; stress adds0.20
USD/oz spread and0.10 USD/oz adverse slippage. Commission and swap are pinned from
original broker assumptions. Current rates/calendar are unverified historical
costs: COST_INCONCLUSIVE persists even when research gates pass.

Trade frequency uses entry UTC, all full months including zero/warmup months;
partial months are separate. Monthly/yearly profit is realized net by exit UTC.
Worst-scenario cost/risk aggregates break qualified ties; WR/RR are descriptive.
Initial10% risk excludes future swap; gaps/swap can exceed admission loss and BE
can close net negative. No-signal/mixed terminal reasons are not proof of future
tradability. No Demo cutover, real-money qualification or profit forecast follows.
