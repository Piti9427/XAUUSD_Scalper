# Selected26b8 T02/#13 — independent acceptance audit

**PARTIAL: keep #13 open.** The terminal-specific timeline and hashed provenance are useful, reproducible evidence. They do not establish the required host/guest elapsed comparison or independent transport-failure chronology. Unknown fields must remain unknown; they are not completed measurements.

Audited published `T02.md`, prior `runs/c22-root-closure-2026-10-28/vm-ap/FINDINGS.md` and its 16-entry hash manifest, current passive `transport-current.json`, `provenance-current.json`, and `capture_current.py` under `runs/c22-issue-closure-2026-10-28/ap/`. All 16 prior manifest hashes match. Current artifact hashes and independently recomputed event ordering are recorded in `ap/independent-t02-audit.json`.

| Acceptance criterion | Evidence and limit | Status |
|---|---|---|
| Exact build/profile/process and aware-UTC provenance; sanitized endpoints | Current process ancestry, binary byte lengths/SHA256, four profile metadata hashes, service source/unit hashes and per-native-line hashes are present. Terminal binary hash identifies exact bytes. The collected `native_builds` values are unclassified build tokens, including OS/native startup references; do not present them as one verified MT5 version. Socket endpoints are hashed. | Provenance captured; human-readable version attribution UNKNOWN |
| Direction of causality and per-terminal versus host-global facts | Native ordering shows scan completion→handoff→native `lost`; process-owned sockets have separate sampled RTT/byte metrics. This establishes native event order. It does not time a kernel transport failure, identify endpoint roles or prove network cause. Current capture explicitly states no independent kernel-loss chronology. Prior report already preserves that limit. | Native sequence complete; actual transport-causality measurement incomplete |
| Host/guest elapsed comparison and bounded network/Wine hypothesis work; missing flags UNKNOWN | Host UTC/NTP is observed. Guest elapsed remains `UNKNOWN_NO_GUEST_CLOCK_PROBE_AUTHORIZED`. A valid host/guest comparison has not been performed. In addition, current host-wall interval ends before `timedatectl`, while host-monotonic interval ends after that subprocess; their numerical difference is not a clock-drift observation. | Incomplete |
| Reproducible bounded report, known/unknown, passive ownership | Existing scripts and current hashed outputs reproduce the bounded native loop timeline without SDK import, second broker reader, service changes or terminal configuration changes. Ranked network/Wine/profile hypotheses and counter-observations are recorded. | PASS |

Minimal next work: correct the host measurement bracket in the passive capture script; define a bounded same-window guest elapsed probe and transport-loss observation protocol. Guest/runtime instrumentation or intrusive experiments still require their applicable approval and flat/noUNKNOWN maintenance conditions. Do not attach a debugger to the armed terminal or pin guessed IPs to manufacture closure.

T03/#14 remains separate: before/after trigger reproduction, a matched fix and 1h repeat/24h rollover observation are not delivered by a timeline audit. Native fill/BE/close evidence also remains separate. No VM write, broker read, financial change or GitHub mutation was performed by this reviewer.

## Root follow-up — corrected same-bracket host clock observation

A new passive two-second observation at2026-10-28T15:20:55.455762+00:00
records monotonic-before/wall/monotonic-after at both endpoints. Host wall
elapsed2.000095781s lies within monotonic elapsed bounds2.000093061–2.000097501s;
wall-minus-monotonic bounds are−1720..2720ns. NTP reports synchronized/EtcUTC.
This corrects the earlier mismatched host bracket. It supports only this short
host observation; it does not prove guest clock behavior or absence of other
time jumps. No guest probe,SDK call,terminal/service mutation or causal transport
measurement occurred. #13 remains PARTIAL for guest elapsed and kernel-loss
chronology. Private reproducible script/output:
`runs/c22-issue-closure-2026-10-28/ap/capture_clock_v2.py` and
`.../host-clock-v2.json`; original evidence is retained.

##29OctoberThai follow-up — sender reconnect and AutoTrading hypotheses falsified

Fresh passive capture finished28Oct18:20:26.186974UTC/29Oct01:20:26Thai.
Sender126749/selected-1c0453 and terminal116183 remain active with unchanged
start times/NRestarts0. Last100cycle records contain80algo_permissions_required
and20duplicate_bar. The latest signal at18:15UTC has raw_direction=0; no eligible
missed trade is inferred from this sample. Journal has no active intent/halt,
but this is not fresh broker flatness proof. SDK calls0/service mutations0.

Independent source trace confirms SDK initialize once before the CLI loop
(`scripts/demo_runtime/cli.py:160`),shutdown only in finally(:235); no per-cycle
login/reinitialize branch. Selected cycle delegates without an SDK reconnect.
Actual flags have terminal_trade_allowed=true,tradeapi_disabled=false,
account_trade_expert=true,connected=false/account_trade_allowed=false. The
identity gate therefore blocks correctly. Disabling that gate,adding initialize
every cycle or removing strategy cooldown does not repair the observed native
connection loop. AutoTrading-off is disproved for this captured snapshot.

Native provenance contains1357handoff/lost events each. First handoff12:00:12.006
followed lost12:00:12.013; handoffs continue through18:20:14.233 without an
inter-handoff gap>60seconds. Sender restart12:50:38 occurs inside that continuous
sequence and did not repair it. Terminal authorization06:49:34/enabled06:49:41
after its earlier restart precedes recurrence at12:00periodic scan; this is
evidence against calling terminal restart a durable fix. Midnight/06:00scans
completed without a loop,so every periodic scan alone is not sufficient either.
Native wall-log order still does not establish kernel-loss chronology or guest
elapsed behavior. Deepest trigger stays UNKNOWN; #13/#14 remain OPEN.

Source: private `ap/provenance-1819.json`; independent read-only source review
performed without VM/SDK/GitHub writes. Next justified experiment measures guest
elapsed and terminal-owned transport under the accepted maintenance boundaries,
then chooses one factor. A short healthy spell cannot satisfy1h+24h/rollover.

##29OctoberThai follow-up — actual unprivileged socket-destroy events

A bounded45.06second passive capture at28Oct20:46:45.192550–20:47:30.253214UTC
used Linux ss events/metadata only,no SDK,sudo,packet payload,guest process,
terminal/runtime/configuration mutation or VM file write. Terminal unit PID/start
remained unchanged.44snapshots contain82owned socket observations.8socket-destroy
notifications match both the exact previously observed socket cookie and TCP
tuple owned by Linux descendant PID116217. Their AP/trading/scan roles remain
UNKNOWN. The event listener was stopped by its observer at the bounded deadline;
returncode−15 is that own-child termination,not a terminal or network failure.

The initial native-log read contained no matching window events. A later
read20:48:57UTC exposed3scan/handoff/lost groups and3enabled messages from that
same window. Log silence is therefore not AP stability evidence. Original and
delayed observations remain separate,not overwritten.

| Native logged handoff wall UTC | Host socket-destroy receipt UTC | Observed wall-stamp difference ms | Native logged handoff→lost ms |
|---|---|---:|---:|
|20:46:56.226|20:46:56.228554|2.554|9|
|20:47:13.072|20:47:13.074746|2.746|6|
|20:47:29.924|20:47:29.927127|3.127|5|

These are correlated observations,not proved causal ordering. Host receipt is
an upper observation bound,not exact kernel failure time; socket destruction
can be intentional,not transport failure. Native guest wall time/perf-counter
alignment and notification latency are not independently established. Missing
retrans/lost fields remain null,notzero. Logged wall elapsed16.846/16.852seconds
versus paired host-receipt monotonic elapsed16.846192712/16.852378623seconds does
not measure the terminal's guest performance counter. Deepest trigger remains
UNKNOWN and AP is not fixed. This removes the earlier collection-capability gap
for unprivileged socket events,not the entire transport-causality/guest-clock gap.

The20ms-after-handoff associations above are a **post-hoc display subset**,not
preregistered flow-role matching or a qualification rule. All8attributed destroy events are
retained. One is stamped329.585ms before a logged handoff; others occur after
enabled messages or later than the displayed20ms subset. Omitting them would
bias the narrative. The complete list of8attributed host receipts and nearest logged native
event are:

| Host destroy receipt UTC | Nearest native logged event | Observed stamp difference ms |
|---|---|---:|
|20:46:48.922939|enabled20:46:48.578|+344.939|
|20:46:55.896415|scan-finished/handoff20:46:56.226|−329.585|
|20:46:56.228554|scan-finished/handoff20:46:56.226|+2.554|
|20:47:05.253167|enabled20:47:04.903|+350.167|
|20:47:13.074746|scan-finished/handoff20:47:13.072|+2.746|
|20:47:22.139699|enabled20:47:21.802|+337.699|
|20:47:29.927127|lost20:47:29.929|−1.873|
|20:47:29.951403|lost20:47:29.929|+22.403|

Nearest-in-time is exploratory alignment only. Every flow role is still UNKNOWN;
even the earlier destruction cannot be called broker transport failure. This
capture neither proves network-first nor rules it out. Future evidence must
identify relevant flow roles and clock/notification bounds before assigning
causality.

The full captured denominator is42parsed host destroy notifications:8attributed
and34unbound. The34were counted but their temporal/ownership witnesses were not
retained by the initial collector. They must not be assumed foreign or absent
from terminal activity; periodic1Hz owner snapshots can miss short-lived target
sockets. Complete terminal-destruction/failure coverage is UNPROVED. V1's
unscoped exclusion_count=0 referred only to the displayed8and was ambiguous;
the preserved V2artifact explicitly separates0attributed omissions from34unbound
plot exclusions. No original capture or V1artifact was rewritten.
Use `all-event-timeline-v2.json` and the manifest's full denominator fields.

A fresh host-only2second control at20:50:40UTC reports NTPSynchronized=yes;
wall-minus-monotonic bounds−3000..3240ns for that observation. It is not guest proof.
Machine evidence/code/hash audit:
`runs/c22-ap-socket-events-2026-10-29/`,including capture,delayed-native,
ownership/correlation audit and host-clock control. No complete packet trace,
broker-current exposure proof or executed native trade was manufactured.

## Exact product build and bounded official-document lookup

An explicit MetaTrader5 product startup line at06:49:22.241UTC identifies
**MetaTrader5 x64 build6281**,line8/SHA256
b30e8c908a860a8d355a8b3ae36ce19ab7b938972ecfb6edb2c022126bddbaae. This is
product-specific,not the earlier unclassified OS/native build-token set. The
20:54:51UTC read still shows terminal unit PID116183/start06:49:04UTC and binary
130,631,232bytes/SHA2566df36024dda3bed25abca84be7cb564ff1a0de92b168acbad2f938b48ff4da45.
Native startup classification is now available; PE resource/terminal API version
and release channel remain independently unverified. No version change occurred.

Context7 returned third-party/unrelated libraries,so the bounded lookup used
MetaQuotes primary pages directly without installing a CLI or escalating access.
The reviewed [Platform Settings](https://www.metatrader5.com/en/terminal/help/startworking/settings)
documents server/proxy and automated-trading controls. This lookup did not
verify an auto-AP-disable configuration key. Do not transplant MT4 data-center
settings,edit an undocumented profile field or pin guessed endpoints as a fix.
The retrieved [official release index](https://www.metatrader5.com/en/releasenotes)
lists build6230 dated24September2026 at its top; this alone does not establish
6281's channel or that a version differential repairs this AP loop. No matched
6281AP fix was verified in this bounded review. Community-login/TLS anecdotes
about a different build are not evidence of this broker AP trigger.

Next defensible work still needs the applicable execution-time approval:
freeze the non-secret existing Wine launch context,measure bounded guest elapsed
alongside this host-event observer,then choose a justified one-factor test.
No new package,runtime,terminal restart,network pin,SDK reader or financial rule
was introduced by the passive evidence work. #13/#14 remain OPEN.
