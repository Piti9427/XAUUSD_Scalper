# Oracle ARM Wine initialization correction — 2026-10-24

## Summary

Wine initialization and four command/process/restart smoke cases passed on the
owner's Oracle ARM64 VM after correcting Box64's Wine reservation handling.
Basic Windows Python and NumPy/MetaTrader5 import probes subsequently passed.
Box64 DynaRec MT5 startup fails independently of the Python SDK. A source-built
QEMU with the upstream trap-number fix now connects to the expected Exness Demo
account, including a cold SDK auto-launch and a restart using QEMU for both
terminal and Python. C22 shadow is now installed as an enabled systemd service,
with execution disabled and a durable audit journal. Usable broker history,
local backup/restore and automatic startup after an owner-approved VM reboot
were verified. Initial post-boot connection interruptions remain recorded;
long-running stability, feed parity, shadow soak, costs and sending cutover
remain unqualified. Telegram is deferred at the owner's request. No order-send
API was called. Trading rules and frozen source pins were not changed.

The owner first ran commands manually, then explicitly approved execution of
the Wine compatibility test and inspection through the existing Termius session.
Initial results were observed in that terminal. The owner subsequently supplied
the SSH target and key path; direct SSH with strict host checking was verified.
The existing key's permissions were restricted to 0600; its contents were never
read. The earlier 24-file initialization and 13-file startup bundles were then
downloaded under the ignored campaign directory and all 37 listed checksums
verified locally. VM timestamps use UTC; this report's date uses Asia/Bangkok.

## Symptom and root cause

Target: Ubuntu 24.04.4 LTS, aarch64, Neoverse-N1, four cores, 4 KiB pages,
kernel initially reported as `6.17.0-1016-oracle`. Box64 v0.4.4 (`2f130fa`)
ran Wine 11.20 amd64 WOW64 from the Kron4ek build. `wine --version` succeeded,
but `wineboot.exe --init` aborted with exit 134:

```text
set_mem_area_state: Assertion `!(size & granularity_mask)' failed.
```

In `src/tools/wine_tools.c`, Box64 supplied a default reservation at `0x10000`
with size `0x8000`. Wine's `virtual_init()` passes preloader reservations into
`set_mem_area_state()`, which requires 64 KiB alignment. The 32 KiB default
violated that contract.

A second defect remained after aligning the default. `get_prereserve()` parsed
`WINEPRELOADRESERVE=start-end` but returned the raw end address as `size` and
rounded the start only to the host page size. Actual Wine children supplied
values such as `140000000-14000d000`; the parser returned size `0x14000d000`
instead of the aligned range length `0x10000`. Child processes still aborted.

An environment-only reservation helped the first process but did not fix the
chain: Wine regenerated the variable for its children, including zero and PE
image ranges. Later `kernel32.dll` failures therefore did not establish that
kernel32 needed replacement. The final successful run loaded it without adding
DLLs. Wine assertions were retained throughout.

Source references: [Box64 v0.4.4 reservation handling](https://github.com/ptitSeb/box64/blob/v0.4.4/src/tools/wine_tools.c),
[Wine 11.20 preloader range parsing](https://github.com/wine-mirror/wine/blob/wine-11.20/loader/preloader.c),
[Wine 11.20 virtual memory initialization](https://github.com/wine-mirror/wine/blob/wine-11.20/dlls/ntdll/unix/virtual.c).

## Fix and experiment ledger

Only Box64's `src/tools/wine_tools.c` changed on the VM: 30 insertions and
12 deletions. The default size became `0x10000`; the parser now calculates
64 KiB aligned end minus aligned start and rejects malformed, reversed, empty
and overflowing ranges. This is a local compatibility patch, not an upstream
release or a change to C22.

| Experiment | Observation | Conclusion |
| --- | --- | --- |
| Original initialization, repeated | Same assertion and SIGABRT | Reliable runtime repro |
| Native GDB | `__assert_fail` / SIGABRT; limited emulated frames | Wine assertion confirmed; stack warning alone did not prove corruption |
| Interpreter mode, existing and fresh prefix | Same assertion; later logs confirmed `BOX64_DYNAREC=0` | DynaRec not required to reproduce; old prefix not required |
| Explicit aligned environment reservation | Initial process progressed; child reset reservation and aborted | Environment workaround incomplete |
| Default-size-only patch | New prefix exited 1; dynamic child ranges still asserted | One-line patch incomplete |
| Extracted actual parser, before parser fix | 11 mismatches across 13 contract cases | Wrong range size/alignment reproduced independently of Wine |
| Same parser cases after fix | 13 passed, zero mismatches | Parser correction verified; these are not 11 independent runtime bugs |
| Original fresh-prefix runtime repro after both fixes | Exit 0, zero assertions, zero kernel32 failures | Original initialization failure no longer reproduced |

The parser harness extracts the actual function from the VM source and compiles
it natively. It checks range arithmetic, not emulator behavior. The separate
Wine tests exercise the full process path. No upstream introduction date or
upstream CI coverage was established. The local readiness gap was accepting
version output as progress before exercising initialization and child processes.

## Validation and recovery evidence

`cmake --build ... --parallel 4` completed with exit 0. Existing `snprintf`
truncation warnings in `core.c`/`sysinfo.c` remain. `git diff --check` on the
Box64 checkout returned 0. Build and installed binary hashes matched:

```text
0015d249b804cc7c0907f7dbb385e578f7ecc917b8c8b12bc0de97d04096a749
```

Fresh successful prefix: `/home/ubuntu/c22-wine-parserfixed.kYWtPT`.
It created nonempty `system.reg`, `user.reg` and `userdef.reg`.

| Smoke case | DynaRec | Expected / observed exit | Marker | Seconds |
| --- | --- | --- | --- | --- |
| `interpreter-exit` | 0 | 17 / 17 | `C22_INTERPRETER_OK` | 9.183 |
| `interpreter-child` | 0 | 0 / 0 | `C22_CHILD_OK` | 9.336 |
| `dynarec-child` | 1 | 0 / 0 | `C22_CHILD_OK` | 6.607 |
| `restart-wineboot` | 1 | 0 / 0 | Exit and absence of assertion/kernel32 failure checked | 6.090 |

All four passed. The fresh initialization used interpreter mode; DynaRec was
validated for child execution and initialization on the existing successful
prefix. This was process restart, not an OS reboot or systemd recovery test.

Evidence directory on the VM:
`/home/ubuntu/c22-oracle-compat-evidence/20261023T182125Z/`.
It contains repro/debugger logs, original/default-only/final source snapshots,
`box64-wine-prereserve.patch`, parser red/green logs and harness, build log,
Wine smoke harness/results, fresh boot log/result, provenance manifest and
`SHA256SUMS`. All 24 listed file checksums were verified on the VM.

- Patch SHA256: `61e5ad7286a67016ea6ce08bcbfc67209b86dbaf3931f38057288c77efbc4a25`.
- Summary SHA256: `8a1323c1bbe944cd02f41a6671a9de5459bd6cb4ab38a84aa4f88b49c1379f8e`.
- Original installed binary retained as `/usr/local/bin/box64.c22-before-64k`.
- Default-only binary retained as `/usr/local/bin/box64.c22-before-parser`.
- Matching source backups retain `.c22-before-64k` and `.c22-before-parser`.

Restoring a backup binary is possible but was not executed; it restores the
corresponding known-failing state. Test prefixes and artifacts were retained as
debug evidence, not promoted to the dedicated C22 production runtime. No
temporary instrumentation was added to the emulator or trading code; Wine
debug channels were scoped to individual test invocations.

## Remaining readiness gates

Fresh boot still logged missing `libEGL.so.1`, OLE/RpcSs and setup errors despite
exit 0. Their impact on GUI/MT5 is unresolved. Next compatibility work must
validate Windows Python, MT5 terminal and SDK on this exact host; these smoke
results cannot substitute for those workloads. Actual OCI free entitlement,
pending-kernel reboot, systemd/boot recovery, monitoring and private backup
restore remain unverified. Retain the one-engineering-day compatibility timebox
and zero-additional-spend constraint.

Owner subsequently clarified that no Windows machine or Windows VPS is
available. The earlier plan's Windows fallback is unavailable. A failed
compatibility timebox therefore leaves a host blocker; it does not authorize
buying a VPS or assuming another executable host.

Continuation preparation downloaded the official Windows x64 Python 3.13.17
runtime ZIP on the VM. Its SHA256 matched the
[Python release manifest](https://www.python.org/ftp/python/3.13.17/windows-3.13.17.json):
`b26ca4b4ee51e157836049934d2b8eabd55939be296f3130254251b6df96ec2f`.
Archive inspection found 3,161 files, including `ensurepip` and pip. The archive
and provenance JSON are under `/home/ubuntu/c22-compat-downloads/`.
MetaTrader5's PyPI metadata listed a CPython 3.13 Windows x64 wheel; that
availability is not proof of import or IPC compatibility under Wine.
The subsequent probe was observed extracting Python into
`/home/ubuntu/c22-wine-parserfixed.kYWtPT/drive_c/tools/python313`, then was
interrupted with `Ctrl+C` while the host harness waited in `subprocess.run()` /
`stdout.read()`. No completed Python runtime or pip verdict was observed. This
is an interrupted run, not a demonstrated Python incompatibility. Computer Use
keyboard actions and screenshots were intermittently unresponsive; the owner
confirmed manually that SSH still answered `pwd`. Before retrying, inspect
`/home/ubuntu/c22-windows-python-result.json` and use direct log files plus a
bounded host wait, rather than an unbounded PIPE read that can wait for output
inherited by Wine descendants. Do not repeat extraction over the existing tree.

The owner then ran bounded manual probes with output redirected directly to
files and supplied their results: `python.exe --version` exited 0 and printed
`Python 3.13.17`; the core probe exited 0 with `C22_PYTHON_CORE_OK`,
`sys.platform=win32`, 8-byte pointers, OpenSSL `3.5.9 29 Sep 2026` and SQLite
`3.50.4`. The core probe exercised an in-memory SQLite create/insert/select.
`python -m pip --version` also exited 0, reporting pip 26.2.2 under
`C:\tools\python313\Lib\site-packages\pip`. These are basic Python checks,
not proof of child-process handling, durable financial persistence or terminal
IPC. The earlier interrupted combined harness remains interrupted.

The hash-pinned binary-only pip install printed successful installation of
NumPy 2.5.4 and MetaTrader5 5.0.6231, then exited 137 with `Killed` and a broken
X connection. Installed metadata and pip's JSON report subsequently confirmed
both versions. The owner's kernel journal query found no OOM entries in the
preceding 20 minutes; memory showed 21 GiB available. This does not establish
the origin of SIGKILL or prove clean installer shutdown. Missing native X11
libraries were logged; their role in that exit remains unproven.

A separate bounded process then exited 0 and printed `IMPORT_START`,
`C22_NUMPY_OK 2.5.4` and `C22_MT5_IMPORT_OK 5.0.6231`. Its NumPy assertion
checked that the float64 sum of `arange(10)` equals 45. This establishes those
imports and one numerical operation on this host, despite the earlier install
shutdown failure. These probes did not call SDK initialization, connect to a
terminal or send orders.

Terminal discovery initially returned zero `terminal64.exe` files. The owner
downloaded the Windows installer linked by the
[MetaQuotes download page](https://www.metaquotes.com/en/download):
`https://download.terminal.free/cdn/web/metaquotes.ltd/mt5/mt5setup.exe`.
HTTP 200 and PE32+ GUI x86-64 format were reported. The received file is
`/home/ubuntu/c22-compat-downloads/mt5-installer.eYBYDp/mt5setup.exe`, with SHA256
`c8c0a73f86c58974df62fb48f8256a099d6698518cf2defc2b3f169773729e22`.
This is an observed artifact hash, not a comparison with a publisher checksum.

The bounded installer invocation used the documented `/auto` and
`/path:C:\tools\mt5-c22-compat` arguments in the tested Wine prefix. It exited
1. Its log reported missing native `libXinerama.so.1`, `libXcomposite.so.1`,
`libXi.so.6`, `libxkbregistry.so.0` and `libXcursor.so.1`, then a broken X
connection. The expected `terminal64.exe` existed and was 130,631,232 bytes.
File presence does not prove completed installation or working terminal IPC.
Ranked hypotheses remain GUI dependency failure, installer finalization or
additional component failure, and display/child-process shutdown after files
were installed. No crash stack was reported for this ordinary nonzero exit;
the next differential addresses the explicitly logged library gaps before a
separate terminal probe. Do not reinstall solely on this exit code.

A native Python `ctypes.CDLL` probe subsequently failed for all five libraries.
The owner then supplied `apt_exit_code=0` and `dpkg-query` results confirming
ARM64 packages `libxcomposite1` 1:0.4.5-1build3, `libxcursor1` 1:1.2.1-1build1,
`libxi6` 2:1.8.1-1build1, `libxinerama1` 2:1.1.4-3build1 and `libxkbregistry0`
1.6.0-1build1 installed. This confirms package installation, not the cause of
the installer exit or terminal/IPC readiness. Subsequent loading verification is
recorded below.

The first explicit terminal IPC probe then printed only `C22_IPC_START` and
exited 124 at the 90-second outer deadline. It used `initialize()` with the
exact installed terminal path, `portable=True` and SDK `timeout=30000` ms.
Neither the initialize return/last-error line nor the SDK shutdown marker was
observed. This places the wait inside the initialize call as observed by the
Python probe, but does not distinguish terminal startup, IPC readiness or a
Wine/SDK blocking path. It is not an SDK-reported error or evidence of broker
parity. No login or order methods were invoked. Inspect remaining processes
and terminal logs before another initialization attempt; do not increase the
timeout or reinstall on this evidence alone.

Post-timeout inspection confirmed `ctypes.CDLL` could load all five native
libraries. The selected process snapshot showed only `wineserver` (PID 1635301,
PPID 1, elapsed 47:32), with no matching terminal or Windows Python process.
Neither the portable install log directory nor the probed default per-user
terminal log paths contained a terminal log. This snapshot was taken after
timeout cleanup and cannot establish whether a child ran during initialization.
The next control launches the same terminal directly without Python/SDK, records
process state while it runs and captures Wine process/exception diagnostics.
The existing wineserver is retained; its presence alone does not establish a
stale-process cause.

The owner requested Computer Use again. After verifying a read-only input marker
and `/home/ubuntu` in Termius, the direct terminal control started at VM-reported
`2026-10-23 19:26:31 UTC`. With DynaRec enabled, the 40-second bounded invocation
exited 139 and reported a core dump / segmentation fault. The log showed the five
X11 libraries loaded through native wrappers. This reproduces a startup failure
without Python or SDK; it does not prove that every SDK timeout shares the same
cause. Log: `/home/ubuntu/c22-mt5-direct-control-cua.log`.

A bounded native GDB run stopped on SIGSEGV in the thread named
`terminal64.exe`, at native PC `0xffffea8cfc98`, instruction `ldrb w1, [x11]`.
Unwinding through generated code was limited, showing an unknown frame and
`memory_data`; the corrupt-stack warning alone is not evidence of stack
corruption. This is a first-stop observation, not proof that this particular
signal is unhandled. Log: `/home/ubuntu/c22-mt5-direct-gdb-1.log`. A continuation
probe distinguished successive Wine fault stops before changing emulator settings.

## MT5 startup differential ledger — unresolved

These probes used the same installed terminal and prefix, without account login
or order methods. Environment changes were scoped to each invocation, with no
permanent rcfile changes. The original startup failure remains unfixed.

| Probe | Observed result | What it establishes |
| --- | --- | --- |
| GDB continuation | First SIGSEGV at `0xffffea8cfc98`, followed by two stops at `0xffffea8d0a50` | Fault handling progresses; batch end is not terminal success |
| Interpreter direct control, 40 seconds | Exit 124; DynaRec disabled in actual process logs | Disabling JIT did not produce startup within the bound; timeout is not a pass |
| Interpreter GDB sample after 20 seconds | `Run()` in `src/emu/x64run.c:112` | Sample was executing interpreter code; progress versus a loop remains unknown |
| Guest fault trace | Exit 139; guest RIP `0x1438f7e85`, access `0xb88a9da9`; Wine dispatches `c0000005`, calls MT5 handler `0x143a63824`, then segfaults | Narrows the failing exception path; first access violation may itself be expected by the executable |
| `SAFEFLAGS=2` alone | Exit 139 | This setting did not fix startup; identical guest path was not established for this run |
| Minimal Windows SEH control | Exit 0; invalid pointer caught as `OSError`, subsequent valid DLL call succeeds | Falsifies the broad claim that all Windows SEH is broken |
| Targeted `DYNAREC_TEST` over `0x143a63800-0x143a63c00` | Range activation logged; first handler returns 1; later fault at `0x144ab7aaf`; exit 5 | Instrumentation changes behavior, but startup still fails; no executed comparison count or equivalence proof |
| `BIGBLOCK=0` alone | Exit 139, same first guest RIP and handler | Smaller blocks alone do not resolve this failure |
| `CALLRET=0` alone | First handler returns 1; later fault at `0x144ab7aaf`, access `0x1002ffdb8`; second handler `0x144efc84b` returns 1; exit 5 | CALL/RET optimization affects the earlier failure path; later startup failure remains |
| Second-block `DYNAREC_TEST` over `0x144ab7a9e-0x144ab7ad4`, with CALLRET disabled | Range activation logged; same later guest RIP/access; exit 5; no mismatch diagnostic observed | Startup remains broken; executed comparison coverage still needs proof |

The minimal SEH control uses Windows Python `ctypes` and
`GetModuleHandleA(NULL)`, then `GetModuleHandleA(0x20)`, then the valid call again.
All four markers through `C22_SEH_RECOVERY_OK` were observed. This follows the
[Python ctypes SEH example](https://docs.python.org/3.13/library/ctypes.html)
and does not exercise MT5's custom handler.

The instrumented comparison and CALLRET-disabled runs both reached Wine's
attempt to launch `winedbg`, which Box64 declined to launch, followed by debugger
error 731. A debugger launch failure follows the later exception; it does not
explain the original first fault. No mismatch diagnostic was observed in the
targeted comparison log. Without instruction coverage evidence, that absence
cannot prove DynaRec and interpreter equivalence.

Raw logs on the VM retain names `c22-mt5-direct-gdb-continue.log`,
`c22-mt5-direct-interpreter-cua.log`, `c22-mt5-interpreter-gdb.log`,
`c22-mt5-direct-gdb-detail.log`, `c22-mt5-showsegv.log`,
`c22-mt5-safeflags.log`, `c22-seh-smoke-v1.log`,
`c22-mt5-handler-compare.log`, `c22-mt5-smallblock.log` and
`c22-mt5-callret0.log`. The minimal control script is
`/home/ubuntu/c22-compat-downloads/c22-seh-smoke-v1.py`.

A separate startup evidence bundle was observed and verified on continuation:
`/home/ubuntu/c22-oracle-compat-evidence/20261023T200520Z-mt5-startup`.
It contains 12 startup/debugger/control logs and the minimal SEH script. All 13
file hashes were read back and checked on the VM. `SHA256SUMS` SHA256 is
`4eaa070323330626cacdc12a4a4760dbd06cb63d6e18e8b42c59b1a058fa1d9a`;
the CALLRET-disabled log SHA256 is
`2a45c53de43057bde906a92e29916ccd17e5ceed6acfacad308ea164e15e19c4`.
This supplements the earlier 24-file initialization bundle without replacing it.

A second-fault GDB command with CALLRET disabled was submitted with a 45-second
outer bound and output path `/home/ubuntu/c22-mt5-secondfault-gdb.log`.
Its output was initially unavailable because Computer Use screenshots remained
unchanged and a focus-recovery call timed out. A later refreshed screenshot
confirmed that GDB continued past the first fault and stopped at the second:
native PC `0xfffff36038d8`, `si_code=2`, `si_addr=0x1002ffdb8`.
Guest bytes around `0x144ab7a9e` were captured, including sign-extension, address
calculation and store instructions. Native unwinding remains limited; batch
completion is not a terminal pass. The subsequent targeted interpreter/DynaRec
comparison was observed in a refreshed screenshot: exit 5, 16,381-byte log,
same second fault and debugger launch error. Its log is
`/home/ubuntu/c22-mt5-secondblock-compare.log`. The range-activation messages
alone do not establish executed comparison coverage. These two new logs are
outside the verified 13-file bundle and have not yet been bundled/checksummed.

Upstream source at the exact tag commit
`2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a` confirms that the compiler injects
`x64test_step` for the selected range, while that function returns early when
`ref->test.test` is false. The comparison routine also deliberately omits CPU
flag comparison. The GDB coverage script was subsequently run; its actual
instruction coverage and cache control are recorded below.
See [range instrumentation](https://github.com/ptitSeb/box64/blob/2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a/src/dynarec/dynarec_native_pass.c#L242)
and [test execution](https://github.com/ptitSeb/box64/blob/2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a/src/emu/x64test.c#L167).
These source facts further limit any conclusion drawn from a silent comparison
log; they do not establish the cause of the MT5 fault.

Arranging Termius beside Codex and exiting Full Screen allowed another input
marker/result refresh, but did not resolve the Computer Use failures: subsequent
coordinate input again returned `noWindowsAvailable`, with stale terminal pixels
and delayed accessibility content. This was an automation access blocker in
addition to the independent MT5 startup failure. Local `~/.ssh/config` exists
but exposes no active Host/HostName/User/Port/IdentityFile/Include directives;
no usable direct SSH target had then been established. The owner later supplied
one and direct SSH now works. No private key contents were read.

The leading unresolved hypothesis is an emulator execution/context mismatch in
MT5's exception-heavy startup. A Wine/MT5 compatibility issue independent of
CALL/RET remains plausible because the second fault survives disabling that
optimization. A later isolated reinstall reproduced the same terminal fault.
The observed native library gaps are resolved, and the passing SEH control rules
out a universal SEH failure. None of these observations justifies changing
trading code, replacing DLLs, removing assertions or declaring host readiness.

## Direct SSH continuation and controls

All controls below use isolated prefixes or the existing compatibility prefix,
with no login or order method calls. No global emulator settings were changed.

| Control | Observed result | Interpretation |
| --- | --- | --- |
| Original second-range coverage probe | 82,986 calls, all in the earlier handler range, none in the requested second range | Prior silent comparison did not exercise the intended range; cache contamination is a hypothesis |
| Same second-range probe with `BOX64_DYNACACHE=0` | Exactly five enabled calls at `0x144ab7a9e`, `aa0`, `aa2`, `aa7`, `aaf`; terminal exit 5 | Correct range now observed; no mismatch printed before the fault, but CPU flags and fault completion are not proved equivalent |
| CALLRET=0, cache disabled | Same second guest fault, exit 5 | Persistent cache is not necessary for the startup failure |
| Fresh Wine 11.20 prefix and one continuous Xvfb session | Wineboot 0, terminal 5, prefix shutdown 0 | Old prefix and lost display are not necessary for the DynaRec failure |
| Fresh Wine 11.0 stable prefix, same terminal hash | Wineboot 0, terminal 5 at the same guest RIP; different stack/access address | Failure is not exclusive to Wine 11.20; this does not qualify another Wine release |
| `NATIVEFLAGS=0` alone, then `DF=0` alone against CALLRET=0/cache-disabled baseline | Each exit 5, same second fault | Neither flag independently fixes this path |
| Reinstall same verified installer into a separate directory | Installer 1; terminal 5; new and original terminal SHA256 identical | Nonzero installer exit follows its launched terminal crash; replacing the payload did not fix it |
| `AVX=0`, then baseline in the same display | Each exit 5, same guest fault/access | Disabling advertised AVX did not resolve startup |
| Full interpreter, 120 seconds | Outer timeout 124; later inspection found MT5 build 6281 startup/compilation log from within that run | A persistent GUI's timeout alone cannot establish startup failure; live IPC still needs verification |
| Interpreter GDB samples at 15-second intervals | Guest old-IP `0x144a8419d`, `0x1446d6d0f`, `0x1446d6d4b` | Guest instructions change; samples alone cannot distinguish repeated work from eventual readiness |
| Interpreter terminal plus DynaRec Python in one display | Fresh startup marker, terminal alive; SDK returned `False`, `(-10005, IPC timeout)` after 15.202 seconds | Process/startup log does not establish usable IPC |
| Only terminal PE image interpreted, Wine libraries on DynaRec | New startup marker after 158.048 seconds; 30-second settle; SDK timed out after 60.394 seconds | This split did not qualify IPC |
| Full interpreter with 180-second settle after a fresh startup marker | Startup marker after 106.032 seconds; SDK timed out after 60.619 seconds | An additional three-minute settle did not fix IPC |
| Whole-image co-simulation on Wine 11.0 | Exit 5, same later fault, no mismatch diagnostic | No runtime instruction-count proof was captured for this wider run; do not infer equivalence |
| Only first handler interpreted, then only faulting block interpreted | Each exit 5 on Wine 11.0 | Neither narrow range independently fixes startup |
| Stock MetaEditor compile under DynaRec on Wine 11.0 | Exit 1, stack-overflow diagnostic | Not a working shortcut for first-run compilation |

The two fresh-prefix controls copied the original terminal directory, including
its logs. Their copied startup log timestamp belongs to the earlier interpreter
run, not to either DynaRec control. Log presence alone must not be counted as a
new successful startup. A separate interpreter/SDK control therefore requires
a fresh timestamp and a live terminal before attempting read-only IPC.

The separate Wine 11.0 archive was verified against the
[publisher release](https://github.com/Kron4ek/Wine-Builds/releases/tag/11.0)
and GitHub asset digest:
`39574efa1132c3ca0d5c77dd2eddbe4a49cca0d6cc2c290ff4924493a1c40314`.
It was extracted beside Wine 11.20, without replacing the original runner.
The reinstalled/original terminal SHA256 is
`6df36024dda3bed25abca84be7cb564ff1a0de92b168acbad2f938b48ff4da45`.

Local application checks were rerun against the unchanged application source:
`make test-demo` passed **126 tests in 70.706 seconds**. Full unittest discovery
ran **1,008 tests in 112.554 seconds: 25 failures, two skips**. Every failure is
in legacy webhook tests; observed reasons include the wall-clock rollover gate
after 20:55 UTC superseding their expected admission/close reason. Those fixtures
use current time. No assertion or trading gate was changed to obtain a pass.
The earlier full-suite pass remains historical evidence, not this run's result. A later unchanged-source rerun outside the rollover window passed **1,008 tests in 116.026 seconds (two skips)**; both raw logs are retained. This confirms clock-dependent test behavior without changing their assertions.

The initialization patch is now retained in
[`deploy/c22-demo/box64-wine-prereserve.patch`](../../deploy/c22-demo/box64-wine-prereserve.patch).
A local fresh-source revalidation applied that exact patch: 11/13 parser cases
failed before, 13/13 passed after, and the patched source matched the VM file
byte for byte. This does not change the unresolved MT5 qualification.

## Independent QEMU control — experimental

QEMU user-mode was prepared under `/home/ubuntu/c22-qemu-control`, using signed
Ubuntu repositories and download/extract only. System packages, binfmt rules and
the original Wine runner were not replaced. Fifty-six amd64 library packages
form a private sysroot; package hashes are retained. QEMU 8.2.2
(`1:8.2.2+ds-0ubuntu1.18`) is a static arm64 binary from Ubuntu Noble updates.
Wine 11.0 was copied and private loader/server shell wrappers explicitly invoke
QEMU, avoiding accidental child execution through the system Box64 handler.
Copied preloaders were disabled and `WINELOADERNOEXEC` used in these wrappers;
this is a different experimental loader arrangement, not a pure one-variable
engine comparison. See [QEMU user-mode documentation](https://www.qemu.org/docs/master/user/main.html).

QEMU/CPU=max command controls returned the expected 17 and 0, and Windows Python
core returned 0. MT5 produced a fresh build 6281 startup marker after 35.012
seconds and stayed alive up to the SDK probe. The SDK returned `False`,
`(-10002, IPC recv failed)` after 1.186 seconds; its process exited 0. That is a
failed connection, not a compatibility pass. A cold SDK launch using the exact
Windows path also failed: target SIGSEGV, outer timeout 124. No Box64 banner was
found in these logs. Wineboot itself returned 0 but reported child segmentation
faults/RpcSs errors, so it does not qualify all Wine services.

With CPU=qemu64, command/Python controls still passed, but the same minimal
Windows SEH control that passed on Box64 exited -11 immediately after
`C22_VALID_DLL_CALL_OK`. The harness stopped before trying MT5. This exposes a
smaller Wine/QEMU exception failure independent of C22 and broker access.
No CPU-model workaround was accepted for deployment.

QEMU 10.2.1 (`1:10.2.1+ds-1ubuntu3.3`, Ubuntu Resolute) was also downloaded and
extracted privately. Its original broad SEH control exited 0 but caught
`0xc000001d` (illegal instruction), rather than the expected access violation.
Wine printed `Got unexpected trap -1`. That marker-based pass was insufficient.
The new manual
[`verify_windows_seh.py`](../../deploy/c22-demo/verify_windows_seh.py)
requires the correct read/write access violation, address `0x20`, and successful
DLL calls before and after each fault. Both cases failed on QEMU 10.2.1 and
passed on the existing Box64 control. The assertions were strengthened to expose
the wrong exception, not relaxed to accept it.

The observed trap number matches the mechanism in upstream QEMU commit
[`586284af4c2cfa90fd61cff414b0deb77acd70f7`](https://github.com/qemu/qemu/commit/586284af4c2cfa90fd61cff414b0deb77acd70f7):
`CPUState.exception_index` has already been cleared when the signal frame is
built. The fix records the hardware vector separately in `env->trap_nr`.
The exact four-file upstream diff is retained as
[`qemu-trapno.patch`](../../deploy/c22-demo/qemu-trapno.patch), SHA256
`59c7698084079d88faac323babad0b5e39f1febfb1de8d650dbe9609c09e83e8`.
No Wine assertion or exception handler was weakened.

A private native build at that commit was tested twice with the same compiler,
dependencies, Wine 11.0, prefix and final probe hash. First, only the upstream
commit was reversed; then it was reapplied and the tracked source checked clean.

| Build | Strict Windows result | Binary SHA256 |
| --- | --- | --- |
| Same source with only the trap fix reversed | 2 failures; both wrong exception and `trapno=-1` | `b01e510e55075d3ace49d772a9cb3411a47173b6dfde594e3c2fd7cc54df1d82` |
| Exact upstream commit, clean tracked source | 2 passed; read/write address and recovery correct; no unexpected trap | `0ef575324ec4d889778b684da84d5d8f1bf2cf7453813dac82777be78866310c` |

This establishes the exception correction at the Windows call site. It does not
establish complete MT5 compatibility. The next terminal/SDK control on this
binary passed command, child, numerical Python and strict SEH controls; MT5
stayed alive, but initialize still returned `(-10005, IPC timeout)` after 30.282
seconds. A subsequent clean-prefix bootstrap did not finish in 55 seconds and
reported RpcSs errors, so that harness stopped before any account login.

The source build and its Python/native dependencies remain under
`/home/ubuntu/c22-qemu-control/source-build`. No system package installation,
binfmt change or sender startup was performed. The QEMU binary is experimental;
its printed version is 11.1.50, not a qualified stable deployment release.

Direct SSH evidence was downloaded as
`runs/c22-oracle-compat-2026-10-24/vm-evidence-ssh-controls.tar.gz`.
All 170 listed file hashes were checked locally. Archive SHA256:
`668bc5ad07e1e7e2e306d9952f8ecd3a2319d943d2c9d125aa00d47fe1f8d409`.
This snapshot precedes the final source-build and later identity probes; those
results must be preserved separately rather than inferred from its manifest.

The first QEMU version probe set `WINELOADERNOEXEC` and lacked an explicit
prefix. It entered Wine initialization instead of printing a version, timed
out and created `/home/ubuntu/.wine`. Inspection found no `terminal64.exe` in
that prefix and no remaining QEMU processes. It was preserved, not deleted.
Subsequent probes require an explicit isolated prefix and bounded termination.
This probe was not a successful version check.

After host compatibility, the existing [C22 Demo runbook](../ops/c22h4-demo.md)
still requires broker identity/history/parity, fresh cost evidence, stopped old
sender and flat account, at least 48 hours/96 complete M15 shadow bars across UTC
midnight, disconnect/restart/boot recovery and owner approval at actual cutover.
Costs remain `COST_INCONCLUSIVE`; profitability remains `INCONCLUSIVE` and real
money remains prohibited. This session did not test trading economics or send
orders. Earlier application correction evidence remains in the
[containment correction report](2026-10-23-c22-demo-containment.md).

## Demo connection and C22 deployment preparation

The successful stack uses Wine 11.0 and the source-built QEMU binary above for
both Windows Python and MT5. Three Wine launchers have private shell wrappers
that invoke QEMU explicitly; copied preloaders are disabled. This avoids silently
routing children through the host's Box64 binfmt handler. The dedicated prefix is
`/home/ubuntu/c22-qemu-demo._g86ow9b`; terminal path is
`C:\tools\mt5-c22-demo\terminal64.exe`. Terminal and data paths were both verified
as `C:\tools\mt5-c22-demo`. No global binfmt or other application service changed.

The generic MT5 installation lacked the owner's broker catalog. The official
Exness installer returned HTTP403 on both hosts. Instead, only `servers.dat`
(connection settings) was copied from the owner's existing Mac installation;
`accounts.dat`, terminal account settings and journals were excluded. The old VM
catalog was backed up before replacement. New catalog SHA256:
`7f095167235df793433811ac9a778ccb4434fc2a85cd0330ddceaa6fc1f80a5e`.
The account credentials were staged separately in a mode0600 private file, never
in the release archive or evidence bundle. No password, login number or server
label is required to interpret the recorded identity checks.

| Experiment | Observed result | Interpretation |
| --- | --- | --- |
| `qemu-broker-catalog` | initialize true, 29.502s; expected Demo/fingerprint, connected, positions0/orders0 | First actual broker connection; hybrid diagnostic client |
| `qemu-only-broker-restart` | initialize true, 12.717s; same identity and flat exposure; no Box64 banner | Both terminal and Python work under the same QEMU build |
| `runtime-cold-sdk` | initialize true, 26.631s; same identity, positions0/orders0; process exit0 | SDK can launch terminal without prestart or GUI cancellation |
| `runtime-cold-sdk-10s` | initialize false, error -10005, 23.985s | Existing 10000ms SDK timeout insufficient on this host |
| `c22-shadow-once` | durable BLOCKED `algo_permissions_required`; outer timeout124 after150s | Shadow incorrectly demanded AutoTrading permission; host wrapper also waited on inherited terminal stdout |
| `c22-shadow-direct-once` | durable BLOCKED `quote_unknown`, execute false, observed positions0, protection flat; process exit1 in48.117s | Corrected shadow can inspect account while AutoTrading remains off; market-data preparation still needed |

Warm initialization is not assumed to fit the old timeout. The shared CLI now
accepts `--initialize-timeout-ms` in1000..120000, default10000 unchanged. Oracle
uses90000. Invalid values fail before runner creation or SDK initialization.
This changes connection patience, not signal timing or the 90-second entry window.
The public CLI regression went red on the unsupported option and then green.

Shadow identity checks now permit read-only observation with AutoTrading off.
Demo login/server/currency/account-mode, connection, capital and journal identity
checks remain mandatory. Execution still requires all permissions; every
send/modify/close boundary retains the strict default `identity()` check.
The regression uses the same frozen BUY fixture that normally produces
`SHADOW_ADMIT`, disables terminal and account trading permissions, and verifies
admission without `order_send`; explicit execution blocks. A mistaken initial
WAIT expectation was corrected to the fixture's existing `SHADOW_ADMIT` outcome,
with stronger readiness/no-send assertions. No failing safety assertion was
removed or weakened.

The first once-run used the existing native host wrapper. Its completed Windows
CLI left stdout inherited by MT5, so the wrapper waited until the outer timeout.
The direct Windows entrypoint returned normally. The Oracle service must invoke
that entrypoint directly with one X display and one systemd control group;
this does not establish that the generic host wrapper has been fixed.

Windows runtime venv `C:\tools\c22-runtime\Scripts\python.exe` was created from
Python3.13.17. Hash-required wheels installed with exit0 in195.714s:
NumPy2.5.3, pandas3.0.5, MetaTrader5 5.0.6231, python-dateutil2.9.0.post0,
six1.17.0 and tzdata2026.2. NumPy/pandas match the local reference environment;
optional pandas_ta is absent on both. Lock SHA256:
`53c986639e90ccecfb190867caa903fb9e1fd6c3e0e4fce146511f810ccef4c4`.
The successful cold probe imported the pinned versions. Package installation and
connection success do not prove trading profitability or long-running stability.

Runtime release `d091bc6b810e792c` contains58 explicitly selected source/config
files and a per-file SHA256 manifest. Archive SHA256:
`17c80b597cfd7e749d25ee42b5916788976b49e7657b19cd331d1125db146f1b`.
All file hashes and frozen strategy pins were verified after extraction. The
manifest records HEAD7356de4 plus the three uncommitted operational corrections
(cli.py, broker.py, runner.py); it does not claim a clean committed release.
No `.env`, private credentials, local financial journal or pending Dobby research
was copied into the release. The new shadow journal is separate; existing local
financial history and user edits remain preserved. Cost evidence is explicitly
`COST_INCONCLUSIVE`, without a forged review timestamp or invented zero costs.

## Persistent shadow service and remaining blockers

`c22-demo-shadow.service` was installed, enabled and started at04:41:37UTC.
The installed unit is the repository's
[`c22-oracle-shadow.service`](../../deploy/c22-demo/c22-oracle-shadow.service).
It runs as ubuntu on the existing VM, checks58 source/config hashes before
start, forces order gate0 and never passes `--execute`. All Wine descendants
belong to the unit's control group. Restart is bounded3/300s with10s delay.
Credentials remain in a separate mode0600 environment file. No new cloud
resource or paid service was provisioned. The owner confirmed that the existing
VM was selected as Free Tier in Oracle's web console; billing/tenancy entitlement
was not independently queried.

The first service used PrivateTmp. That option was removed so a separate Windows
SQLite backup client can share the dedicated Wine server with the watcher.
The old unit and the exact external probe prefix were stopped before restart;
no unrelated service, account or Wine prefix was killed. systemd-analyze verify
passed for the installed shadow/backup/timer units. Existing Oracle monitoring
units produced unrelated executable-bit warnings during verification.

A stop/start preserved the audit journal:189 events before stop,235 after
reconnection,502 by04:50:53UTC. Source history was not reset. Connected cycles
reported execute=false, positions0, protection=flat and `quote_stale`, consistent
with the last broker quote at2026-10-23T20:57:59.584Z and the closed market.
No completed live M15 shadow bar or 48-hour soak was claimed from these cycles.

A real stability blocker appeared during continued observation: terminal log
repeatedly scanned for access points and voluntarily reconnected to Access
Point #1 with99% quality, roughly every17seconds. Only one terminal process was
present, inside the shadow unit's cgroup. C22 correctly alternated flat/stale
quote with connection-unknown states. The current reason
`algo_permissions_required` also covers a disconnected terminal; it must not be
interpreted as permission to enable AutoTrading. This unexpected disconnection
fails the soak gate, even though the process remains alive and reconnects.
Raw broker log excerpts were redacted before inspection.

The old Mac terminal logs showed only4 scans and0 automatic switches onOct23,
with scans hours apart. The same owner's routing catalog therefore does not
alone explain the VM cadence. A Windows clock control under the actual QEMU
build showed five seconds of wall/QPC/monotonic time and5.011s GetTickCount64;
RDTSC advanced about5.003billion ticks. Global clock acceleration was not
observed. Host/Wine uptime was125days, leaving a counter-wrap hypothesis to be
tested separately. A bounded isolated time-namespace experiment may change only
the test process's monotonic/boot-time offset; host UTC and other services are
not changed. No reboot or permanent time-namespace deployment is authorized by
that experiment.

Local daily backup is installed as `c22-demo-backup.service` and an enabled
persistent timer, scheduled02:10UTC with up to300s jitter. It runs the same
Windows SQLite implementation as the writer, using SQLite online backup,
integrity checks, SHA256 and a temporary-file restore check. The first live
backup returned0 in6.739s while the watcher was active. The installed oneshot
also returned Result=success/ExecMainStatus=0. Its snapshot contained239 audit
rows,8kv rows and0pending broker events; checksum
`59e3c92ee0433fa914369ce4c0232c6e1b4551c3964a17c613be98b888de14c3`.
Each snapshot is cumulative; retention keeps the latest7 without pruning the
source financial history. This is not proof that7 daily executions have occurred.
Private object-storage upload, remote retention and cloud download/restore remain
unverified; no bucket was created. Whole-VM recovery was subsequently tested
with explicit owner approval; see the approved reboot record below.

Telegram setup was requested, then explicitly deferred by the owner in favor of
Oracle system setup. A one-off wizard is available on the VM but was not run with
real credentials and is not attached to the service. Its private-chat nonce
pairing helper passed5 local HTTP tests through Postman simulation, including
429/500, wrong nonce/group rejection and existing-webhook rejection. Simulation
request logs verified the actual HTTP paths; this is not live Telegram delivery
proof. No Telegram/Healthchecks account, subscription or external monitor was
created. Postman's owner-mock lookup required login, so the simulation used
fixtures based on official Telegram response shapes. Orbit discovery returned an
HTTP error; official Telegram documentation remained the contract source.

Final application verification after the operational corrections:

- `tests.demo.test_c22h4_cli`:9tests passed, including configurable/default and
  invalid startup budgets, disabled-AutoTrading shadow vs blocked execution,
  and retained Demo identity/connection gates.
- `make test-demo`:130tests in71.453s, OK.
- Full unittest discovery:1012tests in118.144s, OK,2skipped.
- Repository compile, dependency check and lint passed. Global format-check
  still reports the same15 untouched legacy files; changed Python files pass.
- Scoped diff whitespace check passed. Existing user trade-note whitespace and
  unrelated Dobby work were preserved.

Technical status: Demo IPC/history and durable shadow/restart/local backup proven;
automatic boot startup was subsequently verified. Network stability, feed parity,
prospective completed-bar soak, disconnect recovery and external monitoring
remain open. Costs: COST_INCONCLUSIVE.
Profitability: INCONCLUSIVE. Sending cutover still requires real-time owner
approval after the operational and evidence gates; no automatic transition.

The owner's next instruction explicitly deferred Telegram and narrowed current
work to Oracle Free Tier system setup. No real Telegram token was entered,
no test message was sent to Telegram and no notification drop-in was installed.
The wizard remains optional and outside the immutable runtime release.

The existing Mac financial journal was inspected through a read-only SQLite
connection: active=None, pending events0, no safety halt, saved dayOct22 with
reconciled-flat-midnight provenance. A consistent online SQLite backup and exact
copies of both trade-note files were archived privately on the VM; the pending
user notes were not modified. Three file hashes verified after extraction.
Archive SHA256:
`a4eecf0c82a921c6f5aa1169162a6bec0e16624cac4d9b963e46d76f6600fbbd`.
This archive preserves the legacy kv/events schema and does not replace the VM
shadow journal or reset its baseline. Future cloud recovery qualification must
include this preserved financial archive as well as cumulative current journals.

Boot preflight identified another application under userpiti, not ubuntu:
`pm2-piti.service` and nginx are enabled. The saved PM2 entry
`nextjs-vps-project` matches the currently online process. Inspection did not
call pm2 save or change that application's configuration. Reboot still needs
owner approval because it interrupts this other production application.

## Uptime/namespace disproof controls

A no-order SDK control samples terminal connectivity30times,2seconds apart,
with the same Wine/QEMU/terminal/account/catalog and Python venv. Unlike C22,
it does not poll account history, so it isolates the native connection behavior.
The native-uptime control took104.452s including cold startup:17connected and
13disconnected samples. The C22 admission/history loop is not required for the
failure.

Temporary Linux time namespaces permit a per-process monotonic/boot-time offset
without changing host UTC or other services. Controls ran as the actual ubuntu
UID1001, with exact-prefix cleanup and shadow service restoration in finally.
The first wrapper attempts failed before launching the SDK because UID1000 was
incorrect and then a root HOME was inherited. These are harness setup failures,
not connectivity results; runuser resolved the correct user/environment. The
unshare CLI also rejected a negative offset; the Python/kernel namespace API
accepted it. Unprivileged user-namespace creation is denied on this VM; no
system security policy was relaxed.

| Control | Connected / total | Process duration | Result scope |
| --- | --- | --- | --- |
| Native uptime ~125days | 17/30 | 104.452s | Recurrent disconnection reproduced |
| Temporary namespace, uptime5minutes | 30/30 | 104.156s | Stable short observation, UTC unchanged |
| Temporary namespace, uptime30days | 30/30 | 104.404s | Disproves a simple signed-32-bit 24.9day threshold |
| Temporary namespace, uptime60days | 30/30 | 103.501s | Disproves a simple first-49.7day-wrap explanation |

A zero-offset namespace control is required to distinguish namespace membership
from the absolute uptime value. The exact arithmetic inside the closed MT5
binary is not established. Short successful samples are not the required48-hour
soak and do not authorize sending. No permanent namespace helper, global clock
change, root-started trading service or host reboot was installed by these
experiments.

Zero-offset namespace control reproduced12disconnected/18connected samples in
104.457s at the original125day uptime, while30/60day offsets remained30/30
connected. Namespace membership alone is not sufficient. Absolute high uptime
is a verified trigger in this tested stack; the exact MT5/Wine internal counter
arithmetic and threshold remain unproven. Host UTC stayed unchanged in all
controls. Each test stopped the exclusive shadow unit, cleaned its exact Wine
prefix, then restored the original unit; these interruptions are not soak time.

Boot preparation verified kernel6.17.0-1016 currently running, both6.17 and
7.0.0-1013 kernel/initrd images present, and the host reboot-required flag set.
Before any reboot, nginx and the Next.js application both returned HTTP200 on
local ports80/3000. PM2 startup/save state matched its running process. Reboot was
proposed as a bounded operational mitigation and boot-recovery test, with an
additional cumulative financial checkpoint and unit hashes. It is not a claim
of a permanent vendor bug fix or immunity at high future uptime. No automatic
reboot cadence or permanent privileged namespace helper was installed.

## Owner-approved VM reboot and post-boot observation

The owner explicitly approved one reboot with “อนุมัติ reboot ตอนนี้”. The
shared nginx/Next.js impact was disclosed before that approval. Before reboot,
the latest actual shadow cycle was flat, execute=false, at05:28:07.983809UTC.
The shadow unit was stopped and a cumulative checkpoint completed using Windows
SQLite. Its restore-verified snapshot contained1866 audit rows,8kv rows and
0pending events. Snapshot `demo-20261024T052814802108Z.sqlite3` SHA256:
`b6297bef913aef9db8c67374cf3b5b94300e954eef1a6bb0b74034902ebe5b90`.

The approved reboot was issued at05:28:16UTC. Boot ID changed from
`47832162-b458-40ce-8c60-cb25c0a7f920` to
`fef0d2fd-65e3-49e5-b835-70bb5f384a46`; running kernel became
`7.0.0-1013-oracle`. The first successful SSH probe saw uptime14.64s.
nginx, pm2-piti and c22-demo-shadow all started automatically. HTTP HEAD on
local ports80 and3000 returned200 after reboot. The C22 unit remained enabled,
active/running with NRestarts=0. No other application's configuration changed.

The first three-minute observation began with a fresh flat shadow cycle at
05:29:49.746293UTC. Of90 samples,72 were fresh/flat and18 reported connection
unknown (`algo_permissions_required`); execute=false throughout. No failure was
filtered from the result. MT5's redacted network log confirmed repeated
access-point reconnects through05:30:48, then synchronization at05:30:57 and a
scan ending05:31:05 without another automatic switch in the inspected interval.
The entire pre-boot audit prefix (1866 rows, compared by id and exact payload)
survived unchanged; the journal had2062 rows by05:32:50UTC.

These initial interruptions falsify the stronger claim that a short host uptime
alone guarantees stable MT5 connectivity. The earlier namespace differential
remains valid evidence of an uptime-sensitive path, not a complete causal model
or permanent fix. Startup settling, counter initialization and interaction with
the C22 polling workload remain distinct hypotheses. A subsequent observation
keeps configuration unchanged to test whether the interruptions recur after
startup. Neither short interval counts as the required48-hour completed-bar soak.

The unchanged-service extension ran05:34:54.826879–05:37:54.850425UTC:
90/90 samples were fresh, connected, flat and execute=false, with no unexpected
sample. This supports a post-startup improvement only; it does not erase the
18 earlier failures or establish which internal counter caused them.

After that observation, the installed backup oneshot returned
Result=success/ExecMainStatus=0 while the watcher continued. Snapshot
`demo-20261024T053757548358Z.sqlite3` contained2350 audit rows,8kv rows and
0pending events. Its SHA256 was independently recomputed as
`577fdc649d42853d5a84d95495bc9614f18b1f069e4034398a218ab35bde7cad`.
Copying to a temporary restore location and running SQLite integrity_check
returned `ok` with identical table counts. The shadow cycle remained fresh and
flat after backup. The persistent timer remained active; next scheduled run
was2026-10-25 at02:14:01UTC including configured jitter. This is local recovery
proof; no private-bucket upload/download was performed.

The sanitized phase2 evidence bundle was downloaded and independently verified
on the Mac:97 manifest-listed files, zero checksum mismatches. Archive SHA256:
`37fab8fb91afa1cd08eadc1677a17f3dcbd17073bb65530b86f1dd9f8b62fb6f`.
It includes before/after QEMU exception controls, cold SDK/runtime provenance,
history/parity, uptime controls, reboot and backup results, plus the verified
cumulative journal snapshot. Private environment/account files, broker private
logs and credentials were excluded. A second restore on the Mac returned
integrity_check=ok with the same2350/0/8 audit/events/kv counts. Raw artifacts
and the verification result are under ignored
`runs/c22-oracle-compat-2026-10-24/phase2-evidence/` and
`phase2-local-verification.json`; financial history was not pruned.

Final installed unit hashes match the three repository files. Source/config
checks returned0 and systemd-analyze verify returned0. Warnings about executable
permissions on pre-existing Oracle unified-monitoring-agent unit files were
preserved without modifying that unrelated service. C22 remains active/enabled,
NRestarts=0, with the backup timer active/enabled. A final changed-file Ruff check
and format check passed for all5 Python files. An initial `python -m ruff`
attempt was unavailable because this environment installs Ruff as a standalone
executable; using the repository's `.venv/bin/ruff` passed without installing or
changing dependencies.

Current readiness is **Oracle shadow deployed / sending blocked**. Automatic
boot startup and local cumulative recovery are proven. Remaining gates are
long-running connection stability,48h/96completeM15 across UTC midnight, feed
parity review, fresh supported cost evidence, external monitoring and private
cloud recovery. The owner deferred Telegram; that deferral does not silently
waive sending safeguards. Costs remain COST_INCONCLUSIVE and profitability
INCONCLUSIVE. No automatic sending cutover or real-money execution is allowed.
