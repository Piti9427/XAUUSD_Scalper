# B1-FINAL runbook — start, stop, recovery

Scope: `mql5/B1FinalEA.mq5` in the MT5 Strategy Tester on this Mac (Wine). Order execution outside the Tester is disabled in this release. The EA fails `OnInit` on a live chart and on any account that is not Demo. Do not modify the code to bypass this without the separately authorized Demo activation gates. The existing SMC runtime is a separate owner and is not replaced.

Release state and verdicts: [B1-FINAL release package](../research/B1_FINAL_RELEASE_2026-09-27.md).

## Before any run

1. **Refresh the account snapshot.** Config presence is not proof, so run the read-only preflight:

   ```sh
   python3 scripts/ops/run_b1_d_wine.py --script scripts/ops/b1_final_preflight_probe.py --output data/b1_final_release/preflight_snapshot_<date>.json
   .venv/bin/python -m scripts.ops.b1_final_preflight --snapshot data/b1_final_release/preflight_snapshot_<date>.json --output data/b1_final_release/preflight_report_<date>.json
   ```

   Pass `--commission-per-lot`, `--exit-fee-per-lot` and `--admission-reserve-r` with the same values as the EA inputs, so the report sizes exactly like the EA. Run it on a weekday while the market is open: only a fresh tick can show `utc_offset_status=VERIFIED`.

   The wrapper launches the terminal, and the terminal keeps the wrapper's output pipe open. Once `preflight_snapshot_*.json` exists, stop the wrapper. `UNVERIFIED` means the connection failed; it is not an account verdict. `BLOCKED` lists reasons such as identity mismatch, not Demo, not hedging, symbol or spec missing, or foreign exposure. `ACCOUNT_BLOCKED` in a scenario means the minimum lot exceeds the risk budget. Never raise risk, deposit or lot size to get past it.
2. **Close the terminal.** MT5 allows one instance per data folder:

   ```sh
   WINEPREFIX="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5" \
     "/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine" taskkill /IM terminal64.exe
   ```

## Start (Tester)

```sh
python3 -m scripts.ops.mt5_wine_tester run B1FinalEA \
  --sources B1FinalCore.mqh B1FinalState.mqh B1FinalEngine.mqh B1FinalEA.mq5 \
  --output data/b1_final_release/tester/<new-name> --model real_ticks \
  --start 2026.05.14 --end 2026.09.26 --deposit <deposit> \
  --param ExpectedLogin=env:XAUUSD_MT5_LOGIN --param ExpectedServer=env:XAUUSD_MT5_SERVER \
  --param BootstrapState=true "--param=SeedAnchor=2026.05.07 00:00" --param ExitMode=0
```

- `ExitMode=0` is the frozen release (fixed exit). Modes 1 and 2 are research arms only.
- `env:` parameters are read from the ignored `.env` and redacted in `run_manifest.json`.
- `BootstrapState=true` creates a new HWM from current equity. It is an explicit operator action, allowed only when no state file exists and no owned exposure is open.
- Each run collects: the outbox (`*_events.jsonl`), the deal ledger, the consumed bars, the state file, the HTML report, the agent journal, the exact `.ex5` and a manifest.

Check the run afterwards:

```sh
.venv/bin/python -m scripts.research.b1_final_release --run data/b1_final_release/tester/<new-name> --output <new>.json
```

Require `signal_parity.passed` and `reconciliation.passed`. Read `admissions` for the reason behind any zero-trade result.

## Stop

- The Tester exits by itself (`ShutdownTerminal=1`). If the terminal stays up for 60 seconds after the Tester logs `thread finished`, the runner force-closes it and sets `terminal_force_closed_after_finish=true` in the manifest. If MetaEditor hangs on the next compile, run `wineserver -k` first.
- Restore the normal terminal session when finished: start MetaTrader 5, or run the preflight probe, which launches it.

## Recovery rules (built into the engine)

| Situation | Behaviour | Operator action |
|---|---|---|
| State file missing | Entries blocked (`STATE_MISSING_NO_BOOTSTRAP`); positions still managed | Bootstrap only if the account has no owned exposure and a new HWM is intended |
| State corrupt, tampered or version mismatch | Entries blocked; file never overwritten | Keep the file for review. Do not delete it to "reset" the HWM |
| Pending request at restart | Reconciled against positions, then deal history; never resent | None. `REQUEST_NO_FILL` after the reconcile window ends that signal |
| Partial fill | Keeps the confirmed volume; cancels the remainder (no top-up); outstanding owned orders block new risk | If the cancel fails, remove the order at the broker |
| Owned position unknown to state | `INCIDENT` (`UNEXPECTED_OWNED_EXPOSURE`); not closed | Investigate the source; acknowledge only after it is resolved |
| Foreign exposure on symbol | New B1 risk blocked; never touched | Clear or accept externally |
| Missing SL, or fill risk over budget | Owned B1 position closed; incident halt latched | Review, then acknowledge |
| Close failed | `CLOSE_FAILED_CRITICAL`; retried every `CloseRetrySec`; entries blocked | Manual broker intervention |
| DD ≥ 12% of equity HWM | `STOP_NEW_ENTRIES` latched; protected trade kept; survives restart | No automatic restart; needs a reviewed decision |
| Stop modification pending at restart | Confirmed or rejected from the broker's current stop; never resent | None |

To clear an incident, restart the EA with `AcknowledgeIncident=<incident_id>`, taken from the `INCIDENT` event. It clears only when no close is still required.

## Notifications

`scripts/b1_outbox.py` consumes the outbox separately from the EA, so it cannot block position management. Only `FILL_CONFIRMED`, `SL_MODIFIED_CONFIRMED` and `CLOSE_CONFIRMED` events with `confirmed=true` become cards; everything else is diagnostic. The CLI is dry-run and only prints:

```sh
.venv/bin/python -m scripts.b1_outbox --events <dir>/B1FINAL_B1F1_events.jsonl --state <dir>/outbox_state.json
```

A send timeout is stored as `DELIVERY_UNKNOWN` and is not resent automatically. An unavailable sink leaves events pending, in order. Wiring a real Telegram sink is out of scope for this release, and so is sending to real recipients.
