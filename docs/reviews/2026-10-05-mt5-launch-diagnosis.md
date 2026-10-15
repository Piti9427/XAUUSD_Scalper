# MT5 launch diagnosis — root cause not yet confirmed

Read-only host checks authorized in preceding session. No trading API, bot launch, terminal restart, prefix deletion or installation change performed.

## Feedback loop and observed failure

Computer-use `cua.getApp('/Applications/MetaTrader 5.app')` and exact bundle `cua.getApp('net.metaquotes.wine.MetaTrader5')` each returned `Computer Use server error -10005: timeoutReached`. This reproduces inability to obtain a usable app surface through the tool; it does not by itself prove the owner's exact visible symptom. Asked owner whether no window, crash/error, or disconnected window occurs. Prior Python history probe independently reported MT5 `initialize_failed`; that API error is not a GUI diagnosis.

## Evidence

- Host inventory: no trial30/C22 watcher; terminal64 PID65429, launcher parent65427, Wine server2548. Terminal launched2026-10-04T21:00:43+07:00.
- `/usr/bin/sample 65429 2 -file runs/mt5-launch-diagnosis-2026-10-05/terminal-stack.txt` succeeded. Terminal runs Wine11.1, X86-64 translated, macOS27.0. Rosetta thread present. Main thread in CFRunLoop; Windows thread shows repeated wine syscall dispatcher frames. This is insufficient to establish deadlock or its cause.
- `/usr/bin/sample 65427 1 -file runs/mt5-launch-diagnosis-2026-10-05/launcher-stack.txt` succeeded. Launcher AppKit event loop remains alive; Wine dispatch queue waits in NSConcreteTask waitUntilExit, expected for a live child and not alone a defect.
- lsof confirms loaded terminal executable under the expected `net.metaquotes.wine.metatrader5` prefix. Wrong terminal executable/prefix hypothesis is weakened.
- No relevant Wine/terminal64/MetaTrader crash filename found in user DiagnosticReports. Absence does not prove no crash elsewhere.
- Historical20261004 terminal log last inspected lines show repeated reconnects, successful Demo hedging authorization and synchronization with3 positions. This is stale evidence, not current exposure proof, and prevents treating local trial30 active-null as account-wide flatness proof. Account identifier redacted in displayed excerpts. Current broker snapshot unavailable.

## Ranked hypotheses and limits

1. Wine/terminal UI startup stalled: predict clean owner-approved restart makes visible window and API initialize succeed. Untested; no restart permission received.
2. Launcher/prefix mismatch: predict loaded executable differs from expected installation. Loaded path matches, weakening hypothesis.
3. Startup crash: predict recent matching crash report or explicit crash log. Not found in checked directory; remains unconfirmed.

Next: identify actual visible symptom; owner-approved terminal recovery if appropriate, then repeat GUI feedback loop and read-only broker initialize. Do not reinstall/delete Wine prefix or move to UTM based on these observations. No strategy code change justified by this diagnosis.
