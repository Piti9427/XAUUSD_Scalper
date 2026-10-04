# C22H4 history probe — blocked before broker access

2026-10-04 implementation session. Read-only probe launched using existing Wine host wrapper, explicit Demo credentials kept in environment; no journal or order API in probe.

Observed process exit1: `wine: cannot find the server port: 0x0000044c`. No broker rates or parity results produced. Sandbox also denied process inventory (`ps`: operation not permitted); current trial30 watcher state remains unverified.

Gate status: broker M1 maximum/depth, >=201 complete H4, bootstrap <60s, archive-overlap per-signal admission/direction/ATR/macro/levels **unverified**. No fallback selected. Offline implementation preserves broker-only deep bootstrap with fail-closed warmup; no execution or existing watcher/journal changes. Next: exclusive terminal read-only probe outside blocked Wine context, review divergent bars, then shadow protocol in `docs/ops/c22h4-demo.md`.
