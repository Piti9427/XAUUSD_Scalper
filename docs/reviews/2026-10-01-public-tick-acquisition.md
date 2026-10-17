# Public XAUUSDm archive acquisition

13 monthly ZIP archives acquired Sep2024-Sep2025. Ten discovery months Sep2024-Jun2025 fully audited:49,581,644 Bid/Ask ticks,19,050 canonical Bid M15 bars. Jul-Sep2025 remain zipped, no prices/indicators/trades evaluated; nonempty holdout coverage remains unverified. Goal not achieved; no candidate adopted.

## Sources

- [Exness tick history](https://get.exness.help/hc/en-us/articles/360021547851-Tick-history): indicative public Bid/Ask history; suffix m denotes Standard. Does not prove target Demo server/feed or execution parity.
- [Exness API](https://get.exness.help/hc/en-us/articles/27866287512476-Exness-API): region-dependent access; not required for this acquisition.
- [Repository archive endpoint documentation](https://github.com/terrylica/exness-data-preprocess/blob/main/docs/EXNESS_DATA_SOURCES.md): located URL template. Downloaded actual monthly ZIP payloads directly; no external repository code installed or run. Endpoint provenance inferred from repository documentation and validated provider/symbol fields; official ownership of ex2archive domain not independently proven.
- [MT5 copy_ticks_range](https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py): earlier read-only Demo history probe returned zero ticks on each of seven days Oct1-7,2025. Zero ticks do not prove history coverage.

## Reproduction and preserved evidence

```sh
.venv/bin/python -m scripts.research.public_exness_archive --output data/b1_public_exness_2024_09_2025_09
.venv/bin/python -m scripts.research.run_strategy_campaign --dataset data/b1_public_exness_2024_09_2025_09 --output data/strategy_public_activation_campaign_2026_10_01 --campaign activation --screen --stop-on-pass
```

Second command records original executed invocation; subsequent code versions must use a new output path. Frozen source snapshots, protocol and hashes preserve actual run versions.

Local dataset archive-manifest.json/dataset.json record URLs, ZIP SHA256, discovery tick/day counts, canonical bar counts, tape/bar hashes and assumed broker specs. importer-source.py and importer-source.json preserve actual importer version. Discovery first/last ticks:2024-09-01T22:05:06.129Z /2025-06-30T23:59:59.180Z. Every quoted tick retained in source order; Bid M1 assembled from quotes; only complete15-M1 groups form M15. No inferred Ask or forward fill.

Historical broker leverage/contract specs borrowed from archived2026 Demo manifest, explicitly assumptions. Base commission0 and unmodeled historical swap are not verified actual all-in costs. Stress extra spread0.20/oz, adverse market-fill slippage0.10/oz.

Activation288 contracts on ten discovery months found zero qualifiers. New dataset core full net-$6.41/DD48.40%; D48 net-$141.11/DD81.84%. These results weaken conclusions drawn from reused2026 tape alone.

Sealed Jul-Sep2025 holdout predates already-used2026 research. It is historical holdout, not prospective validation. Downloading13 archives does not yet meet verified>=12 nonempty months. No holdout selection, no Demo eligibility claim. No orders or notifications sent.
