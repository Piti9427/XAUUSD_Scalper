# Standalone SMC research challenger

Research-only `smc_m15_v1`. No MT5, sender, notifier, Demo gate change or real-money path.
Contract: `CORE_STRATEGY.md`6.37; [implementation spec](../specs/2026-10-08-smc-strategy-implementation-plan.md).

## Historical comparison

Default input is the verified frozen four-strategy paired archive, ending at its original cutoff. No "through today" acquisition claim. This reuses discovery history, not independent holdout. The runner first verifies archive/input/source/result attestations and reruns the two archived **swap-inclusive** C22 cells to exact full-result parity. It then evaluates C22 and SMC at common new costs (slippage0.10 in both views, total extra spread0.20 in stress), each fromUSD200 continuously. Historical broker costs remain unverified.

```bash
.venv/bin/python3 -m scripts.research.smc_challenger_campaign --output runs/smc-challenger-<run-id> --workers 2
```

`--workers 1` limits memory by running fresh repeats sequentially. Workers2 re-open mmap tapes; they do not run account chunks concurrently. `--max-cells 1` stops after one main comparison cell and returns PARTIAL/exit3. A subsequent call with the same output resumes verified cells. Default4 cells: C22/SMC × base/stress, always modeled swap, all require full-result repeat. Sources/config/runtime/input drift blocks resume; use a new output after code changes, retain prior artifacts.

Outputs: immutable `protocol.json`, source/input/runtime pins, `signals.json` with funnel and causal candidate IDs, `cells/*.json` with trades/swap/equity/DD witnesses/admission reasons, `repeat/*.json`, checkpoint and `COMPLETE.json`. COMPLETE means computation complete; conclusion remains `DESCRIPTIVE_ONLY_NO_SELECTION`, costs `COST_INCONCLUSIVE`. No weighted rank, DD concession or frequency target establishes qualification. Output is restricted to repository ignored `runs/`, and cannot overlap input/baseline.

## Explicit custom input bundle

Use `--input <bundle>` with `manifest.json`, `bars.csv` (`bar_open_utc`), `tape/{time,bid,ask}.npy`. Times are ordered int64 epoch milliseconds; quotes finite/positive, Ask>=Bid. Bars are unique aligned UTC Bid M15 with valid OHLC, sealed by requested cutoff. Retain causal macro/structure warmup prefix in bars and corresponding input provenance. The manifest's bar basis is an input attestation, not independent reconstruction of all M1 minutes. Use the existing canonical importer to produce bars; never fabricate coverage.

Required manifest fields:

- `schema: smc_input_v1`, `kind: historical_discovery`, `requested_start_utc`, `requested_end_utc`. Start must be UTC midnight for canonical offline day baseline. End exclusive for quotes and replay; no post-cutoff data.
- `calendar: conservative_utc_96_bars_v1`, `bar_basis: UTC_Bid_M1_15_of_15`. Asian28 slots; previous day96 slots, missing pools unavailable. This deliberately conservative research calendar may exclude PDH/PDL around ordinary market breaks; no inferred broker session schedule.
- `broker`: trade_contract_size, trade_tick_size, volume_min/max/step, leverage, point, swap_mode1, swap_long, swap_short and swap_rollover3days (MT5 business-day enum1–5). Unsupported mode/metadata blocks; zero short rate must be explicit.
- `costs.base` and `costs.stress`: explicit extra_spread0/0.2, slippage0.1, commission_per_lot. USD/oz price costs and USD/lot/roundtrip commission. No silent defaults.
- `cost_basis`: nonempty quote_source, swap_source, commission_source and slippage_basis=`declared_assumption`.
- `cost_basis.commission_unit`: `USD_per_lot_round_trip`. Missing cost keys or units block rather than use `Costs` defaults.
- `artifacts`: relative file->SHA256 for bars and all three tape arrays plus any provenance files. Paths cannot escape bundle. Normal historical mode still requires verified archived baseline parity via `--baseline`.

Swap uses signed points and UTC-midnight preceding-business-day convention in `rollover.py`: Wednesday triple posts Thursday, weekend rules explicit, entry exactly at rollover owes no prior debit. Current rates/calendar are modeled sensitivity, not historical entitlement. Do not enter invented `holding_days` charges or omit swap when metadata is absent.

## Synthetic diagnostics

Explicit `--fixture --input <synthetic-bundle>` requires `kind: synthetic_fixture`; status is FIXTURE_COMPLETE, not historical COMPLETE. This checks interfaces/serialization/resume on synthetic quotes and skips historical archive parity with `baseline_parity:false`. Both cost+swap views remain mandatory. Synthetic fixture artifacts cannot qualify a strategy.

## Implementation seam and operational boundaries

Frozen replay's immediate transform overwrites anchors. New adapter binds the same event-loop bytecode to a private dictionary containing a prepared-entry transform; this preserves sweep anchors without copying engine code or mutating global bindings seen by C22. Differential regression checks compare complete results when anchors are identical. SELL wick is converted to Ask side at the scenario's first post-close quote before canonical grid/risk math. Canonical conservative floating-point rounding can add an extra tick; it remains included in admission.

Offline baseline/circuit semantics remain canonical. Source hashes passing does not imply Demo gate changes are permitted. `make bot-execute`, `make bot-run`, current C22 contract, Trial30 rollback and cost attestation remain unchanged. No campaign sends Telegram signals. Implementation tests, economic replay, statistical qualification, broker parity, shadow and cutover are separate claims.

Validation:

```bash
.venv/bin/python3 -m unittest tests.test_smc_challenger tests.test_smc_challenger_adapter tests.test_smc_challenger_campaign
.venv/bin/python3 -m unittest discover -s tests
```
