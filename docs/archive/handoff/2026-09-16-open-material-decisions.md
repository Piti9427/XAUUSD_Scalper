# Open material decisions (foundation story 48)

**Status:** Explicit registry — none of these may be silently converted into approved trading rules.  
**Source:** `docs/specs/gold-playbook-foundation.md` § Further Notes  
**Branch evidence:** `feature/smc-v2-hardening`  
**Updated:** 2026-09-16

Agents and operators MUST leave these OPEN until a versioned decision + behavioral examples land. Implementation may use temporary conservative defaults only when the foundation already named them; defaults ≠ settlement.

| Topic | Settled so far | Still open (do not invent) |
| --- | --- | --- |
| Protected swing / CHoCH | M5 CHoCH required; latest fractal alone insufficient | HH/HL/LH/LL construction, protected-swing choice, internal/external scope, init/ties/recovery |
| MSS qualification | Displacement + FVG required | Single-candle body-ratio on CHoCH break?, weak first break, no silent volatility threshold |
| Sweep / pool lifecycle | Wick rejection, known pool, untouched TP | Exact touch quote side, repeated sweep/consumption, invalidation, cancel-if-TP-touched-before-fill |
| Fibonacci anchors | Log-only; OTE research 62–79% | Price-leg / anchor selection, freeze time; no future swing anchors |
| Pending / session timing | TTL 4 M5 bars; session windows | TTL origin/inclusivity, session-end, server expiry, cancel latency |
| Account risk accounting | 0.5%/trade; 2 losses or 1% day; 5% DD; whole-account risk | Open-risk budget details, cash-flow/credit handling, daily-halt disposition, manual no-SL policy |
| Cash flows / intervention | Separate from bot edge; disclose | Pause/rebase on deposit/withdrawal/credit (pause proposal ≠ confirmed) |
| Data provenance | Need M5/H1/ticks + USD HIGH news | Source coverage, feed reconciliation, point-in-time news, proxy acceptance |
| Statistical protocol | 95% lower bounds; net expectancy >0; win p >50%; no quota | One- vs two-sided, bootstrap details, sample sufficiency, $ vs R, stress magnitudes, freeze dates |

## Gate rule

Closing any row requires a dated decision note under `docs/adr/` or `docs/handoff/` with examples. Until then: fail closed / skip setup / mark `INCONCLUSIVE` — never invent a PASS criterion after seeing outcomes.

## Related closed software boundaries (not settlements of the table above)

- Story 49 real-money dual approval: `scripts/smc/real_money_approval.py`
- SetupDecision reject reasons: `evaluate_smc_setup`
- Live Exness / Oracle / Demo 12w: still open operational gates on issue #1
